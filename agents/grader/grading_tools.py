"""Structured-output tools for the grader agent.

The grader is forced to call one of these instead of replying in prose, so
its verdict is always machine-parseable JSON rather than something we'd need
to regex out of a text response.
"""

import json
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

_captured: dict[str, Any] = {}

from agents.grader.explore_scorers import CODE_DIMENSIONS

# The rubric's seven dimensions, still scored 0-5 each, still out of 35 -- what
# changed in Unit 2 is who answers them. Five are now computed in
# agents/grader/explore_scorers.py; the LLM is only asked for the two below.
# (schema_compliance was removed earlier for the same reason -- a pure
# structural check enforced by validate_explorer_output. See schemas.py.)
JUDGED_DIMENSIONS = [
    "context_narrative_quality",
    "interaction_contract_quality",
]

EXPLORE_DIMENSIONS = [
    "semantic_primary_rate",
    "coverage_completeness",
    "strategy_validation",
    "dynamic_content_flagging",
    "context_narrative_quality",
    "multi_strategy_coverage",
    "interaction_contract_quality",
]

assert set(EXPLORE_DIMENSIONS) == set(CODE_DIMENSIONS) | set(JUDGED_DIMENSIONS)

_EXPLORE_SCHEMA = {
    "type": "object",
    "properties": {
        "dimensions": {
            "type": "object",
            "properties": {d: {"type": "integer", "minimum": 0, "maximum": 5} for d in JUDGED_DIMENSIONS},
            "required": JUDGED_DIMENSIONS,
            "additionalProperties": False,
        },
        "critical_failures": {"type": "array", "items": {"type": "string"}},
        "expectation_results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "expectation_id": {"type": "string"},
                    "passed": {"type": "boolean"},
                    "evidence": {"type": "string"},
                },
                "required": ["expectation_id", "passed", "evidence"],
            },
        },
    },
    "required": ["dimensions", "critical_failures", "expectation_results"],
}


@tool("submit_explore_grade", "Submit your final explore-mode grading verdict. Call this exactly once, last.", _EXPLORE_SCHEMA)
async def submit_explore_grade(args: dict[str, Any]) -> dict[str, Any]:
    _captured["explore"] = args
    return {"content": [{"type": "text", "text": "recorded"}]}


_WRITER_SCHEMA = {
    "type": "object",
    "properties": {
        "expectation_results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "expectation_id": {"type": "string"},
                    "passed": {"type": "boolean"},
                    "evidence": {"type": "string"},
                },
                "required": ["expectation_id", "passed", "evidence"],
            },
        },
        "critical_failures": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["expectation_results", "critical_failures"],
}


@tool("submit_writer_grade", "Submit your final writer-mode grading verdict. Call this exactly once, last.", _WRITER_SCHEMA)
async def submit_writer_grade(args: dict[str, Any]) -> dict[str, Any]:
    _captured["writer"] = args
    return {"content": [{"type": "text", "text": "recorded"}]}


def take_captured(mode: str) -> dict[str, Any]:
    result = _captured.pop(mode, None)
    if result is None:
        raise RuntimeError(f"Grader never called submit_{mode}_grade")
    return result


grading_server = create_sdk_mcp_server(
    name="grading",
    version="1.0.0",
    tools=[submit_explore_grade, submit_writer_grade],
)
