"""Structured-output tools for the grader agent.

The grader is forced to call one of these instead of replying in prose, so
its verdict is always machine-parseable JSON rather than something we'd need
to regex out of a text response.
"""

import json
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

_captured: dict[str, Any] = {}

EXPLORE_DIMENSIONS = [
    # schema_compliance deliberately excluded: it's a pure structural check,
    # now enforced deterministically by agents.shared.schemas.validate_explorer_output
    # before the LLM ever sees the output. See schemas.py module docstring.
    "semantic_primary_rate",
    "coverage_completeness",
    "strategy_validation",
    "dynamic_content_flagging",
    "context_narrative_quality",
    "multi_strategy_coverage",
    "interaction_contract_quality",
]

_EXPLORE_SCHEMA = {
    "type": "object",
    "properties": {
        "dimensions": {
            "type": "object",
            "properties": {d: {"type": "integer", "minimum": 0, "maximum": 5} for d in EXPLORE_DIMENSIONS},
            "required": EXPLORE_DIMENSIONS,
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
