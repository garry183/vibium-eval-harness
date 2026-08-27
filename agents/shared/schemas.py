"""Shared data shapes written/read across the pipeline. Every agent boundary
passes JSON matching one of these, never free-form prose -- that's what lets
the grader check the writer's work and the runner check the grader's gate
without re-deriving anything by eye.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


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
    score: Optional[int] = None  # explore mode: 0-40
    band: Optional[str] = None  # explore mode: A-F
    pass_rate: Optional[float] = None  # writer mode: 0.0-1.0
    results: list[ExpectationResult] = field(default_factory=list)
    critical_failures: list[str] = field(default_factory=list)
    gate_passed: bool = False

    def to_json(self) -> dict[str, Any]:
        return asdict(self)
