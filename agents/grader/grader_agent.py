"""Grader agent: scores explorer or writer output against a golden file of
declarative, plain-English expectations. Two modes, one agent, because the
underlying judgment call is the same shape both times -- "does the evidence
in front of me satisfy this claim" -- just against a different rubric.
"""

import argparse
import asyncio
import json
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query

from agents.grader.explore_scorers import flatten, score_deterministic
from agents.grader.grading_tools import EXPLORE_DIMENSIONS, grading_server, take_captured
from agents.grader.run_log import record_run
from agents.grader.static_checks import check_writer_files
from agents.shared.config import EVALS_DIR, MODELS, OUTPUT_DIR, TESTS_DIR, band_for_score
from agents.shared.schemas import validate_explorer_output
from evals.dataset.loader import load_sample

EXPLORE_SYSTEM_PROMPT = """You are the explore-grader. You score an explorer agent's output against a fixed rubric so a writer agent downstream can trust it without re-verifying the live page itself.

Most of the rubric has already been answered deterministically and is not yours to score. element-map.json's structural shape, the semantic-primary rate, coverage against the answer key, count/confidence coherence, multi-match flagging and fallback coverage are all computed in code before you are called. Do not re-check any of them, and do not comment on them.

Score exactly these 2 dimensions 0-5 from the element-map.json and context.md you're given:
- context_narrative_quality: is context.md a clear, accurate prose summary that adds something a reader could not get from the JSON -- or is it the JSON restated?
- interaction_contract_quality: for elements that trigger navigation or a state change, is that consequence recorded anywhere? (The schema has no field for this, which is why it is still judged rather than checked -- read the notes and prose.)

Also flag critical_failures, but only judgment-based ones: something wrong that no field check would catch. Locator-type, count and coverage failures are already collected in code -- do not repeat them.

Then check each expectation from the golden case against the evidence and record whether it passed, with a one-line evidence quote.

Call submit_explore_grade exactly once, at the end, with your full verdict. Do not call it more than once, and do not explain your reasoning in text afterward -- the tool call is the final answer."""


WRITER_SYSTEM_PROMPT = """You are the writer-grader. You score generated \
test files against a golden list of expectations -- fail fast on evidence \
of low-quality or stub output.

TODO/stub markers, hardcoded URLs, missing layers, and time.sleep() calls \
have already been checked deterministically -- don't re-check those. Focus \
on what actually needs judgment: non-semantic locators used where a \
semantic one was available in the element map, and whether the golden \
expectations are genuinely satisfied by the file contents (not just \
superficially present).

Check each golden expectation against the actual file contents you're \
given and record pass/fail with a one-line evidence quote. List any \
judgment-based issue you find as a critical_failure even if no expectation \
directly names it.

Call submit_writer_grade exactly once, at the end, with your full verdict. \
Do not call it more than once, and do not explain your reasoning in text \
afterward -- the tool call is the final answer."""


def _load_golden_case(golden_file: str, name: str) -> dict:
    data = json.loads((EVALS_DIR / golden_file).read_text())
    for case in data["cases"]:
        if case["name"] == name:
            return case
    raise ValueError(f"No golden case named '{name}' in {golden_file}")


async def grade_explore(page: str) -> dict:
    case = _load_golden_case("explore-golden.json", page)
    out_dir = OUTPUT_DIR / page
    element_map = (out_dir / "element-map.json").read_text()
    context_md = (out_dir / "context.md").read_text()

    parsed = json.loads(element_map)
    schema_errors = validate_explorer_output(parsed)

    # The answer key from Unit 1. Without it coverage_completeness has nothing
    # to compare against, so say so loudly rather than scoring a quiet zero.
    try:
        target = load_sample(page).target
        target_errors: list[str] = []
    except (FileNotFoundError, ValueError) as exc:
        target, target_errors = None, [
            f"no usable target for page '{page}' ({exc}) -- coverage_completeness is unscoreable"
        ]

    code_results = score_deterministic(parsed, target)
    code_scores, code_criticals, code_notes = flatten(code_results)

    prompt = (
        f"Golden case:\n{json.dumps(case, indent=2)}\n\n"
        f"element-map.json:\n{element_map}\n\n"
        f"context.md:\n{context_md}\n"
    )
    options = ClaudeAgentOptions(
        system_prompt=EXPLORE_SYSTEM_PROMPT,
        mcp_servers={"grading": grading_server},
        tools=["mcp__grading__submit_explore_grade"],  # judges only the evidence handed to it, can't go read/browse more
        allowed_tools=["mcp__grading__submit_explore_grade"],
        strict_mcp_config=True,  # otherwise the CLI also loads MCP servers from user/project settings
        setting_sources=[],  # isolation mode -- otherwise the CLI also loads the user's ~/.claude/CLAUDE.md etc.
        model=MODELS["grader"],
    )
    async for _ in query(prompt=prompt, options=options):
        pass

    verdict = take_captured("explore")
    dimensions = {**code_scores, **verdict["dimensions"]}
    score = sum(dimensions[d] for d in EXPLORE_DIMENSIONS)
    band = band_for_score(score)
    all_critical = [*schema_errors, *target_errors, *code_criticals, *verdict["critical_failures"]]
    gate_passed = band in ("A", "B") and not all_critical

    result = {
        "mode": "explore",
        "target": page,
        "score": score,
        "band": band,
        "dimensions": dimensions,
        "scored_by": {d: ("code" if d in code_scores else "llm") for d in EXPLORE_DIMENSIONS},
        "scorer_notes": code_notes,
        "critical_failures": all_critical,
        "results": verdict["expectation_results"],
        "gate_passed": gate_passed,
    }
    (out_dir / "explore-grading.json").write_text(json.dumps(result, indent=2))
    record_run("explore", result)
    return result


async def grade_writer(suite: str) -> dict:
    case = _load_golden_case("writer-golden.json", suite)
    page_files = sorted((TESTS_DIR / "pages").glob(f"*{suite}*.py"))
    module_files = sorted((TESTS_DIR / "modules").glob(f"*{suite}*.py"))
    fixture_files = sorted((TESTS_DIR / "fixtures").glob(f"*{suite}*.py"))
    spec_files = sorted((TESTS_DIR / "specs").glob(f"test_{suite}*.py"))
    catalogue_files = sorted((TESTS_DIR / "test-cases").glob(f"{suite}.testcases.md"))
    layer_files = {
        "page": page_files, "module": module_files, "fixture": fixture_files,
        "spec": spec_files, "catalogue": catalogue_files,
    }
    static_failures = check_writer_files(suite, layer_files)

    all_files = [*page_files, *module_files, *fixture_files, *spec_files, *catalogue_files]
    file_dump = "\n\n".join(
        f"--- {f.relative_to(TESTS_DIR.parent)} ---\n{f.read_text()}" for f in all_files
    )

    prompt = f"Golden case:\n{json.dumps(case, indent=2)}\n\nGenerated files:\n{file_dump}\n"
    options = ClaudeAgentOptions(
        system_prompt=WRITER_SYSTEM_PROMPT,
        mcp_servers={"grading": grading_server},
        tools=["mcp__grading__submit_writer_grade"],  # judges only the evidence handed to it, can't go read/browse more
        allowed_tools=["mcp__grading__submit_writer_grade"],
        strict_mcp_config=True,  # otherwise the CLI also loads MCP servers from user/project settings
        setting_sources=[],  # isolation mode -- otherwise the CLI also loads the user's ~/.claude/CLAUDE.md etc.
        model=MODELS["grader"],
    )
    async for _ in query(prompt=prompt, options=options):
        pass

    verdict = take_captured("writer")
    total = len(verdict["expectation_results"])
    passed = sum(1 for r in verdict["expectation_results"] if r["passed"])
    pass_rate = passed / total if total else 0.0
    all_critical = [*static_failures, *verdict["critical_failures"]]
    gate_passed = pass_rate == 1.0 and not all_critical

    result = {
        "mode": "writer",
        "target": suite,
        "pass_rate": pass_rate,
        "critical_failures": all_critical,
        "results": verdict["expectation_results"],
        "gate_passed": gate_passed,
    }
    (TESTS_DIR / "test-cases" / f"{suite}-grading.json").write_text(json.dumps(result, indent=2))
    record_run("writer", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["explore", "writer"], required=True)
    parser.add_argument("--target", required=True, help="page name (explore mode) or suite name (writer mode)")
    args = parser.parse_args()

    if args.mode == "explore":
        result = asyncio.run(grade_explore(args.target))
    else:
        result = asyncio.run(grade_writer(args.target))

    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["gate_passed"] else 1)


if __name__ == "__main__":
    main()
