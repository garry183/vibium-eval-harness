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

from agents.grader.grading_tools import EXPLORE_DIMENSIONS, grading_server, take_captured
from agents.shared.config import EVALS_DIR, EXPLORE_GRADE_BANDS, MODELS, OUTPUT_DIR, TESTS_DIR

EXPLORE_SYSTEM_PROMPT = """You are the explore-grader. You score an \
explorer agent's output against a fixed rubric so a writer agent downstream \
can trust it without re-verifying the live page itself.

Score each of these 8 dimensions 0-5 based on the element-map.json and \
context.md you're given:
- schema_compliance: does element-map.json match the required shape exactly?
- semantic_primary_rate: what fraction of elements have a semantic (not css/xpath) primary?
- coverage_completeness: does the map cover the elements a page like this should have?
- strategy_validation: are strategy counts/confidence scores plausible given the evidence shown?
- dynamic_content_flagging: are repeated/dynamic elements (e.g. one-per-card buttons) correctly flagged rather than mis-treated as single ambiguous locators?
- context_narrative_quality: is context.md a clear, accurate prose summary, not a restatement of the JSON?
- multi_strategy_coverage: do elements have a fallback strategy (or_chain) when the primary alone might be fragile?
- interaction_contract_quality: for elements that trigger navigation/state changes, is that noted?

Also flag critical_failures: any element whose PRIMARY strategy is css/xpath, \
or whose primary strategy has count > 1 (ambiguous).

Then check each expectation from the golden case against the evidence and \
record whether it passed, with a one-line evidence quote.

Call submit_explore_grade exactly once, at the end, with your full verdict. \
Do not call it more than once, and do not explain your reasoning in text \
afterward -- the tool call is the final answer."""

WRITER_SYSTEM_PROMPT = """You are the writer-grader. You score generated \
test files against a golden list of expectations -- fail fast on evidence \
of low-quality or stub output.

Look for: TODO/stub markers, hardcoded URLs (anything not routed through \
config), non-semantic locators used where a semantic one was available in \
the element map, missing one of the 4 required layers (page object, \
module, fixture, spec), and time.sleep() calls (forbidden -- explicit waits \
only).

Check each golden expectation against the actual file contents you're \
given and record pass/fail with a one-line evidence quote. List any of the \
issues above as critical_failures even if no expectation directly names them.

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
    score = sum(verdict["dimensions"][d] for d in EXPLORE_DIMENSIONS)
    band = next((b for b, (lo, hi) in EXPLORE_GRADE_BANDS.items() if lo <= score <= hi), "F")
    gate_passed = band in ("A", "B") and not verdict["critical_failures"]

    result = {
        "mode": "explore",
        "target": page,
        "score": score,
        "band": band,
        "dimensions": verdict["dimensions"],
        "critical_failures": verdict["critical_failures"],
        "results": verdict["expectation_results"],
        "gate_passed": gate_passed,
    }
    (out_dir / "explore-grading.json").write_text(json.dumps(result, indent=2))
    return result


async def grade_writer(suite: str) -> dict:
    case = _load_golden_case("writer-golden.json", suite)
    page_files = sorted((TESTS_DIR / "pages").glob(f"*{suite}*.py"))
    module_files = sorted((TESTS_DIR / "modules").glob(f"*{suite}*.py"))
    fixture_files = sorted((TESTS_DIR / "fixtures").glob(f"*{suite}*.py"))
    spec_files = sorted((TESTS_DIR / "specs").glob(f"test_{suite}*.py"))
    catalogue_files = sorted((TESTS_DIR / "test-cases").glob(f"{suite}.testcases.md"))
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
    gate_passed = pass_rate == 1.0 and not verdict["critical_failures"]

    result = {
        "mode": "writer",
        "target": suite,
        "pass_rate": pass_rate,
        "critical_failures": verdict["critical_failures"],
        "results": verdict["expectation_results"],
        "gate_passed": gate_passed,
    }
    (TESTS_DIR / "test-cases" / f"{suite}-grading.json").write_text(json.dumps(result, indent=2))
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
