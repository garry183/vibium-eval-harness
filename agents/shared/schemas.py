"""Shared data shapes written/read across the pipeline. Every agent boundary
passes JSON matching one of these, never free-form prose -- that's what lets
the grader check the writer's work and the runner check the grader's gate
without re-deriving anything by eye.

ELEMENT_MAP_SCHEMA + validate_explorer_output are the enforcement half of
that claim: schema_compliance used to be one of the grader's 8 LLM-judged
dimensions, which meant "does this JSON match the required shape" -- a pure
structural question -- was being answered by an LLM instead of a validator.
It's now a deterministic pre-check the explore-grader runs before scoring
anything, so a malformed element-map fails the gate outright rather than
costing a judged point.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

import jsonschema


@dataclass
class LocatorStrategy:
    type: str  # "role" | "label" | "text" | "placeholder" | "testid" | "css" | "xpath"
    selector: str
    count: int
    confidence: int  # 1-5
    note: Optional[str] = None  # required when selector text != accessible name


@dataclass
class ElementRecord:
    name: str
    role: str
    strategies: list[LocatorStrategy]
    primary: Optional[LocatorStrategy]
    or_chain: Optional[str]
    accessibility_node: dict[str, Any]
    testability_gap: bool = False
    gap_note: Optional[str] = None


@dataclass
class ExplorerOutput:
    page: str
    url: str
    viewport: str
    crawled_at: str
    stats: dict[str, int]
    elements: list[ElementRecord]

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


_STRATEGY_SCHEMA = {
    "type": "object",
    "required": ["type", "selector", "count", "confidence"],
    "properties": {
        "type": {"enum": ["role", "label", "text", "placeholder", "testid", "css", "xpath"]},
        "selector": {"type": "string"},
        "count": {"type": "integer", "minimum": 0},
        "confidence": {"type": "integer", "minimum": 1, "maximum": 5},
        "note": {"type": ["string", "null"]},
    },
}

ELEMENT_MAP_SCHEMA = {
    "type": "object",
    "required": ["page", "url", "viewport", "crawled_at", "stats", "elements"],
    "properties": {
        "page": {"type": "string"},
        "url": {"type": "string"},
        "viewport": {"type": "string"},
        "crawled_at": {"type": "string"},
        "stats": {
            "type": "object",
            "required": ["total", "with_primary", "gaps"],
            "properties": {
                "total": {"type": "integer"},
                "with_primary": {"type": "integer"},
                "gaps": {"type": "integer"},
            },
        },
        "elements": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "name", "role", "strategies", "primary", "or_chain",
                    "accessibility_node", "testability_gap",
                ],
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                    "strategies": {"type": "array", "items": _STRATEGY_SCHEMA},
                    "primary": {"anyOf": [{"type": "null"}, _STRATEGY_SCHEMA]},
                    "or_chain": {"type": ["string", "null"]},
                    "accessibility_node": {"type": "object"},
                    "testability_gap": {"type": "boolean"},
                    "gap_note": {"type": ["string", "null"]},
                },
            },
        },
    },
}


def validate_explorer_output(data: dict) -> list[str]:
    """Structural validation of an explorer element-map against
    ELEMENT_MAP_SCHEMA. Returns human-readable error strings; empty list
    means the shape is valid (says nothing about content quality -- that's
    still the LLM rubric's job).
    """
    validator = jsonschema.Draft202012Validator(ELEMENT_MAP_SCHEMA)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    return [f"{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors]


@dataclass
class Expectation:
    id: str
    text: str
    category: str
    severity: str  # HIGH | MEDIUM | LOW


@dataclass
class GoldenCase:
    id: str
    name: str
    url: str
    description: str
    expectations: list[Expectation]


@dataclass
class ExpectationResult:
    expectation_id: str
    text: str
    passed: bool
    evidence: str


@dataclass
class GradingResult:
    mode: str  # "explore" | "writer"
    target: str  # page name or suite name
    score: Optional[int] = None  # explore mode: 0-35
    band: Optional[str] = None  # explore mode: A-F
    pass_rate: Optional[float] = None  # writer mode: 0.0-1.0
    results: list[ExpectationResult] = field(default_factory=list)
    critical_failures: list[str] = field(default_factory=list)
    gate_passed: bool = False

    def to_json(self) -> dict[str, Any]:
        return asdict(self)
