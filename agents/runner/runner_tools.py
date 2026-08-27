"""Structured-output tool the runner uses to report its classification of a
single test failure, so the outer Python loop can decide what to do next
(re-verify vs. leave as an intentionally-documented xfail) without parsing
prose.
"""

from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

_captured: dict[str, Any] = {}

CATEGORIES = ["selector_rot", "assertion_mismatch", "timing", "test_data", "real_bug"]

_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "root_cause": {"type": "string"},
        "fix_applied": {"type": "string"},
        "ticket_note": {"type": "string"},
    },
    "required": ["category", "root_cause", "fix_applied"],
}


@tool(
    "submit_classification",
    "Submit your classification and fix summary for this one failing test. "
    "Call this exactly once, after you've already applied the fix (or, for "
    "real_bug, after you've marked the test xfail) -- not before.",
    _SCHEMA,
)
async def submit_classification(args: dict[str, Any]) -> dict[str, Any]:
    _captured["classification"] = args
    return {"content": [{"type": "text", "text": "recorded"}]}


def take_classification() -> dict[str, Any]:
    result = _captured.pop("classification", None)
    if result is None:
        raise RuntimeError("Runner never called submit_classification")
    return result


runner_server = create_sdk_mcp_server(
    name="runner",
    version="1.0.0",
    tools=[submit_classification],
)
