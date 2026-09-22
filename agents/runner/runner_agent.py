"""Runner agent: executes the suite, classifies every failure into one of 5
fixed categories, fixes what should be fixed, re-verifies per-test, then
re-runs the full suite once more. A "real_bug" classification is never
edited away -- it gets marked xfail with a root-cause note instead.
"""

import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, ToolUseBlock, query

from agents.runner import scope_guard
from agents.runner.runner_tools import runner_server, take_classification
from agents.shared.config import MODELS, OUTPUT_DIR, ROOT, TESTS_DIR

SYSTEM_PROMPT = """You are the runner agent. You are given ONE failing \
pytest test, its traceback, the generated source files for that page, and \
the explorer's element-map.json (ground truth for real locators).

Classify the failure into exactly one category:
- selector_rot: the locator no longer matches anything, or matches the \
  wrong thing, but the underlying app behavior is otherwise correct. Fix \
  it by re-deriving the locator from element-map.json and editing the \
  Page Object.
- assertion_mismatch: the locator is fine but the spec asserts the wrong \
  expected value (e.g. stale copy). Fix the assertion to match the \
  documented correct behavior (only if element-map.json or context.md \
  supports the correct value -- otherwise treat as real_bug instead).
- timing: a race condition -- element not yet actionable when interacted \
  with. Fix with an explicit Playwright wait (`expect(...).to_be_visible()` \
  before acting), never a hardcoded sleep and never just raising a timeout.
- test_data: the test depends on state that wasn't set up (e.g. cart not \
  seeded). Fix in the fixture/module layer, not the spec.
- real_bug: the application itself is behaving incorrectly relative to \
  documented/expected behavior. Do NOT edit the assertion to match the \
  broken behavior. Instead add `@pytest.mark.xfail(reason="<root cause>, \
  see element-map.json/context.md for expected behavior")` directly above \
  the failing test function in the spec file.

Two hard rules, both non-negotiable:
- Touch ONLY what this one failure implicates. If you notice a sibling \
  locator/test that *could* benefit from the same pattern, name it in \
  root_cause as a follow-up suggestion -- do not edit it. An unrelated \
  passing test is out of scope even if the improvement seems obviously \
  correct; it wasn't reviewed for this failure and re-verifying it isn't \
  part of this loop.
- root_cause and fix_applied must describe only what you actually observed \
  in the traceback and files you were given THIS turn. Never write "observed \
  in CI" or reference any run, session, or environment other than the one \
  you're in right now -- you have no visibility into CI or prior sessions, \
  and inventing that provenance is worse than admitting you don't know.

Apply the fix using the Edit tool BEFORE calling submit_classification -- \
the classification call is your final action, not your first."""


def _run_pytest(node_ids: list[str]) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        report_path = Path(tmp.name)
    cmd = [
        sys.executable, "-m", "pytest",
        *node_ids,
        "--json-report", f"--json-report-file={report_path}",
        "-q",
    ]
    subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if not report_path.exists():
        raise RuntimeError("pytest did not produce a JSON report -- check pytest-json-report is installed")
    report = json.loads(report_path.read_text())
    report_path.unlink(missing_ok=True)
    return report


def _failed_tests(report: dict) -> list[dict]:
    # "error" is a setup/teardown failure (e.g. a fixture's goto timing out) --
    # just as broken as "failed", only raised outside the test body.
    return [t for t in report.get("tests", []) if t.get("outcome") in ("failed", "error")]


def _collection_errors(report: dict) -> list[dict]:
    return [c for c in report.get("collectors", []) if c.get("outcome") == "failed"]


def _longrepr(test: dict) -> str:
    for stage in ("setup", "call", "teardown"):
        text = test.get(stage, {}).get("longrepr")
        if text:
            return text
    return "n/a"


def _page_files(page: str) -> dict[str, Path]:
    return {
        "page_object": TESTS_DIR / "pages" / f"{page}_page.py",
        "module": TESTS_DIR / "modules" / f"{page}_module.py",
        "fixtures": TESTS_DIR / "fixtures" / f"{page}_fixtures.py",
        "spec": TESTS_DIR / "specs" / f"test_{page}.py",
    }


async def _fix_one(page: str, failure: dict, correction_note: str | None = None) -> dict:
    files = _page_files(page)
    file_dump = "\n\n".join(
        f"--- {rel} ---\n{path.read_text()}" for rel, path in files.items() if path.exists()
    )
    element_map = (OUTPUT_DIR / page / "element-map.json").read_text()

    prompt = (
        f"Failing test: {failure['nodeid']}\n\n"
        f"Traceback:\n{_longrepr(failure)}\n\n"
        f"element-map.json:\n{element_map}\n\n"
        f"Generated files:\n{file_dump}\n"
    )
    if correction_note:
        prompt += f"\n{correction_note}\n"
    tool_names = ["Read", "Edit", "Glob", "mcp__runner__submit_classification"]
    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"runner": runner_server},
        tools=tool_names,  # no Bash, no Write -- runner edits existing files, never invents new ones or shells out
        allowed_tools=tool_names,
        strict_mcp_config=True,  # otherwise the CLI also loads MCP servers from user/project settings
        setting_sources=[],  # isolation mode -- otherwise the CLI also loads the user's ~/.claude/CLAUDE.md etc.
        permission_mode="acceptEdits",
        cwd=str(ROOT),
        model=MODELS["runner"],
    )

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"[runner] {block.text}")
                elif isinstance(block, ToolUseBlock):
                    print(f"[runner] tool: {block.name}")

    return take_classification()


async def _fix_one_guarded(page: str, failure: dict) -> tuple[dict, str | None]:
    """Runs _fix_one, then checks the Page Object edit against the scope
    guard. On violation: revert, retry once with a corrective prompt naming
    exactly what's out of scope. If the retry still violates, revert again
    and return an escalation note instead of a silent pass.

    Returns (classification, escalation_note). escalation_note is None when
    the fix stayed in scope (first try or after one corrected retry).
    """
    page_object_path = _page_files(page)["page_object"]
    spec_path = _page_files(page)["spec"]
    module_path = _page_files(page)["module"]

    before = page_object_path.read_text() if page_object_path.exists() else None
    classification = await _fix_one(page, failure)

    if before is None or not page_object_path.exists():
        return classification, None  # nothing to guard -- fix didn't touch a page object at all

    after = page_object_path.read_text()
    if after == before:
        return classification, None  # page object untouched -- no scope question to ask

    try:
        changed = scope_guard.changed_properties(before, after)
        allowed = scope_guard.allowed_properties(
            test_name=scope_guard.test_name_from_nodeid(failure["nodeid"]),
            traceback_text=_longrepr(failure),
            page_object_source=after,
            spec_source=spec_path.read_text() if spec_path.exists() else "",
            module_source=module_path.read_text() if module_path.exists() else None,
        )
    except SyntaxError:
        return classification, None  # can't statically parse -- don't block the pipeline on an analysis edge case

    violation = changed - allowed if allowed is not None else set()
    if not violation:
        return classification, None

    print(f"[runner] scope guard: reverting -- touched {sorted(violation)}, not implicated by this failure")
    page_object_path.write_text(before)
    correction = (
        f"Your previous edit changed these properties, but this failure's evidence only "
        f"implicates {sorted(allowed) if allowed else '(none identifiable)'}: {sorted(violation)}. "
        f"That edit has been reverted. Redo the fix touching ONLY the properties this "
        f"failure's traceback actually names -- do not carry over the out-of-scope change."
    )
    classification = await _fix_one(page, failure, correction_note=correction)

    if not page_object_path.exists():
        return classification, None
    after2 = page_object_path.read_text()
    changed2 = scope_guard.changed_properties(before, after2) if after2 != before else set()
    violation2 = changed2 - allowed if allowed is not None else set()
    if violation2:
        print(f"[runner] scope guard: retry still touched {sorted(violation2)} -- reverting and escalating")
        page_object_path.write_text(before)
        return classification, (
            f"Scope violation persisted after one corrective retry (touched {sorted(violation2)}, "
            f"allowed {sorted(allowed) if allowed else '(none identifiable)'}). Reverted to the "
            f"pre-fix state and left failing rather than accept an out-of-scope edit."
        )
    return classification, None


async def run_and_fix(page: str) -> bool:
    spec_node = f"tests/specs/test_{page}.py"
    print(f"[runner] initial run: {spec_node}")
    report = _run_pytest([spec_node])
    failures = _failed_tests(report)

    log_lines = [f"# Fix log -- {page}", ""]

    # A module that fails to import yields zero test entries, which would
    # otherwise read as a clean run. The runner can only fix tests, not
    # collection, so stop here and say so.
    collection_errors = _collection_errors(report)
    if collection_errors:
        log_lines.append("Collection failed -- no tests ran, nothing to classify.")
        for c in collection_errors:
            log_lines += ["", f"## {c.get('nodeid')}", "```", c.get("longrepr", "n/a"), "```"]
        _write_log(page, log_lines)
        print("[runner] collection failed")
        return False

    if not failures and report.get("exitcode") != 0:
        log_lines.append(f"pytest exited {report.get('exitcode')} with no failed tests (e.g. none collected).")
        _write_log(page, log_lines)
        print(f"[runner] pytest exit code {report.get('exitcode')}")
        return False

    if not failures:
        log_lines.append("Initial run was clean. No fixes needed.")
        _write_log(page, log_lines)
        print("[runner] clean on first run")
        return True

    for failure in failures:
        nodeid = failure["nodeid"]

        # All failures above were captured from one batch run, before any
        # fix was applied. An earlier fix in this same loop can incidentally
        # resolve a later one (e.g. two tests share the same broken
        # locator) -- re-check before spending a classification call, so
        # the agent isn't handed a stale traceback for an already-fixed
        # test and left to invent a reason for the mismatch.
        precheck = _run_pytest([nodeid])
        if bool(precheck["summary"].get("passed")):
            print(f"[runner] already resolved by an earlier fix this run: {nodeid}")
            log_lines += [
                f"## {nodeid}",
                "- **Category**: n/a -- resolved as a side effect of an earlier fix in this run",
                "- **Re-verified**: PASS",
                "",
            ]
            continue

        print(f"[runner] classifying failure: {nodeid}")
        classification, escalation_note = await _fix_one_guarded(page, failure)
        category = classification["category"]

        print(f"[runner] re-verifying: {nodeid}")
        reverify = _run_pytest([nodeid])
        reverified_passed = bool(reverify["summary"].get("passed"))

        log_lines += [
            f"## {nodeid}",
            f"- **Category**: {category}",
            f"- **Root cause**: {classification['root_cause']}",
            f"- **Fix applied**: {classification['fix_applied']}",
            f"- **Re-verified**: {'PASS' if reverified_passed else 'still failing / xfail'}",
        ]
        if category == "real_bug":
            log_lines.append(f"- **Ticket note**: {classification.get('ticket_note', 'none provided')}")
        if escalation_note:
            log_lines.append(f"- **SCOPE GUARD ESCALATION**: {escalation_note}")
        log_lines.append("")

    print("[runner] full re-run after fixes")
    final_report = _run_pytest([spec_node])
    # Exit code, not the failed count: 0 covers xfail-marked real bugs but
    # rejects setup errors, collection errors, and an empty run.
    final_passed = final_report.get("exitcode") == 0

    log_lines.append(f"## Final full-suite result: {'GREEN' if final_passed else 'STILL RED'}")
    _write_log(page, log_lines)
    return final_passed


def _write_log(page: str, lines: list[str]) -> None:
    out = TESTS_DIR / "test-cases" / f"{page}-fix-log.md"
    out.write_text("\n".join(lines))
    print(f"[runner] wrote {out}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", required=True)
    args = parser.parse_args()
    ok = asyncio.run(run_and_fix(args.page))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
