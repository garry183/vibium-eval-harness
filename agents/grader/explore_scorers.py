"""Deterministic scorers for the explore rubric -- Unit 2.

Five of the seven judged dimensions never needed judgment. Each one asks a
question two competent engineers could not disagree on given the same
element-map, so each is answered here by reading fields instead of by an API
call: zero variance, zero cost, and no calibration debt to pay off in Unit 5.

The rubric is *converted*, not deleted. Every dimension still scores 0-5 and
the total is still out of 35, so EXPLORE_GRADE_BANDS and the band >= B gate
are untouched -- only the answerer changed. This is the schema_compliance
precedent (see agents/shared/schemas.py) applied to the rest of the list.

What stayed with the LLM, and why:

  * context_narrative_quality -- "is this prose a clear summary or a
    restatement of the JSON" is an opinion about writing. No field carries it.

  * interaction_contract_quality -- judged *under protest*. Whether an element
    triggers navigation is a hard fact about the page, but ElementRecord has no
    field for it, so a code scorer has nothing to read. The fix is a schema
    field, not a cleverer scorer; logged here rather than made in this unit.

One rule inherited from Unit 0 shapes strategy_validation: a recorded
``count: 0`` is not evidence. ``vibium_tools.py:98`` raises TimeoutError on
no-match and never returns empty, so any zero in an element-map was inferred
by the agent from an exception, not measured. "The query timed out" and "the
element does not exist" are different statements, and a scorer that treats
them as one is counting a guess.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# The schema's own strategy enum, split on the only axis that matters here: a
# semantic locator describes what the element *is* to a user; css/xpath
# describe where it currently sits in a tree.
SEMANTIC_TYPES = frozenset({"role", "label", "text", "placeholder", "testid"})
NON_SEMANTIC_TYPES = frozenset({"css", "xpath"})

CODE_DIMENSIONS = [
    "semantic_primary_rate",
    "coverage_completeness",
    "strategy_validation",
    "dynamic_content_flagging",
    "multi_strategy_coverage",
]

_TIMEOUT_HINTS = ("timed out", "timeout", "no match", "not verified", "unverified")


@dataclass
class DimensionResult:
    """One dimension's deterministic verdict. `notes` explain the score;
    `critical_failures` are merged into the grader's hard-gate list."""

    score: int
    notes: list[str] = field(default_factory=list)
    critical_failures: list[str] = field(default_factory=list)


def _scale(good: int, total: int) -> int:
    """Fraction -> 0-5, keeping the original rubric's scale intact.

    math.floor(x + 0.5), not round(): Python rounds halves to even, so 1 of 2
    would score 2 and 3 of 6 would score 3 for the same ratio. A grader whose
    output depends on the parity of the result is not one you want to explain.
    """
    if total <= 0:
        return 0
    return max(0, min(5, math.floor(5 * good / total + 0.5)))


def _strategies(el: dict) -> list[dict]:
    return el.get("strategies") or []


def _count_is_measured(strategy: dict) -> bool:
    """A count you can build an assertion on. Null was never executed; zero
    came from an exception, not a measurement (see module docstring)."""
    count = strategy.get("count")
    return isinstance(count, int) and not isinstance(count, bool) and count > 0


def _unmeasured_reason(strategy: dict) -> str | None:
    count = strategy.get("count")
    note = (strategy.get("note") or "").lower()
    if count is None:
        return "count is null -- strategy was asserted, never executed"
    if count == 0:
        if any(hint in note for hint in _TIMEOUT_HINTS):
            return (
                "count=0 attributed to a timeout -- vibium_tools.py:98 raises on no-match "
                "and never returns empty, so this zero was inferred, not measured"
            )
        return "count=0 with no provenance note -- cannot tell a real no-match from a timeout"
    return None


# ---------------------------------------------------------------------------
# 1. semantic_primary_rate
# ---------------------------------------------------------------------------
def score_semantic_primary_rate(element_map: dict, target: dict | None = None) -> DimensionResult:
    """What fraction of elements have a semantic (not css/xpath) primary?

    Pure arithmetic over a string field the explorer already wrote down.
    """
    elements = element_map.get("elements") or []
    semantic = 0
    criticals: list[str] = []

    for el in elements:
        name = el.get("name", "<unnamed>")
        primary = el.get("primary")
        if not primary:
            criticals.append(f"{name}: no primary strategy")
            continue
        if primary.get("type") in SEMANTIC_TYPES:
            semantic += 1
        else:
            criticals.append(
                f"{name}: primary is {primary.get('type')} "
                f"('{primary.get('selector')}') -- non-semantic primaries are a hard failure"
            )

    notes = [f"{semantic}/{len(elements)} elements have a semantic primary"]
    return DimensionResult(_scale(semantic, len(elements)), notes, criticals)


# ---------------------------------------------------------------------------
# 2. coverage_completeness
# ---------------------------------------------------------------------------
def _target_entries(target: dict) -> list[tuple[str, set[str]]]:
    entries = []
    for el in target.get("elements", []):
        known = set(el.get("correct_primary") or []) | set(el.get("acceptable_fallback") or [])
        entries.append((el.get("name", ""), known))
    return entries


def _covers(mapped: dict, name: str, known_selectors: set[str]) -> bool:
    """Match on a selector the answer key recognises first, name second.
    Selector match is the stronger signal -- element names are invented by the
    explorer and two runs rarely agree on them.
    """
    if any(s.get("selector") in known_selectors for s in _strategies(mapped)):
        return True
    return mapped.get("name", "").strip().lower() == name.strip().lower()


def score_coverage_completeness(element_map: dict, target: dict | None = None) -> DimensionResult:
    """Did the map find the elements the answer key says are on this page?

    This was judgment only while there was nothing to compare against. Unit 1's
    hand-authored target.json turned it into set membership.
    """
    if not target:
        return DimensionResult(
            0, ["no target supplied -- coverage is not scoreable without an answer key"]
        )

    mapped = element_map.get("elements") or []
    entries = _target_entries(target)
    found = 0
    criticals: list[str] = []
    matched_names: set[str] = set()

    for name, known in entries:
        hits = [m for m in mapped if _covers(m, name, known)]
        if hits:
            found += 1
            matched_names.update(m.get("name") for m in hits)
        else:
            criticals.append(f"missing from element-map: {name}")

    notes = [f"{found}/{len(entries)} target elements present in the map"]
    extra = [m.get("name") for m in mapped if m.get("name") not in matched_names]
    if extra:
        notes.append(
            f"{len(extra)} element(s) not in the answer key (not penalised): {', '.join(extra)}"
        )

    return DimensionResult(_scale(found, len(entries)), notes, criticals)


# ---------------------------------------------------------------------------
# 3. strategy_validation
# ---------------------------------------------------------------------------
def score_strategy_validation(element_map: dict, target: dict | None = None) -> DimensionResult:
    """Are the recorded counts and confidences internally coherent, and is the
    primary actually one of the strategies that was run?

    Offline checks only. Re-resolving every locator against the frozen page is
    Unit 3's job; this unit refuses to score a locator it never ran as if it
    had been.
    """
    elements = element_map.get("elements") or []
    total = 0
    sound = 0
    notes: list[str] = []
    criticals: list[str] = []

    for el in elements:
        name = el.get("name", "<unnamed>")
        strategies = _strategies(el)

        for s in strategies:
            total += 1
            problem = _unmeasured_reason(s)
            if not problem:
                sound += 1
                continue
            notes.append(f"{name}/{s.get('selector')}: {problem}")
            confidence = s.get("confidence")
            if isinstance(confidence, int) and confidence >= 3:
                criticals.append(
                    f"{name}: '{s.get('selector')}' is unverified "
                    f"({problem.split(' --')[0]}) yet carries confidence {confidence}"
                )

        primary = el.get("primary")
        if not primary:
            continue
        if not any(
            s.get("selector") == primary.get("selector") and s.get("type") == primary.get("type")
            for s in strategies
        ):
            criticals.append(
                f"{name}: primary '{primary.get('selector')}' is not among the listed strategies"
            )
        pcount = primary.get("count")
        if pcount is None:
            criticals.append(f"{name}: primary '{primary.get('selector')}' has no verified count")
        elif pcount == 0:
            criticals.append(f"{name}: primary '{primary.get('selector')}' resolves to nothing")
        elif pcount > 1:
            criticals.append(
                f"{name}: primary '{primary.get('selector')}' is ambiguous (count={pcount})"
            )

    notes.insert(0, f"{sound}/{total} strategies carry a measured count")
    return DimensionResult(_scale(sound, total), notes, criticals)


# ---------------------------------------------------------------------------
# 4. dynamic_content_flagging
# ---------------------------------------------------------------------------
def score_dynamic_content_flagging(element_map: dict, target: dict | None = None) -> DimensionResult:
    """When a locator matches many elements, did the map say so -- or file it
    as a single broken locator?

    "count > 1 and nothing acknowledges it" is two fields and a comparison.
    """
    elements = element_map.get("elements") or []
    criticals: list[str] = []
    ambiguous = 0
    handled = 0

    for el in elements:
        repeats = [s for s in _strategies(el) if isinstance(s.get("count"), int) and s["count"] > 1]
        if not repeats:
            continue
        ambiguous += 1
        name = el.get("name", "<unnamed>")
        acknowledged = (
            bool(el.get("testability_gap"))
            or bool(el.get("gap_note"))
            or any(s.get("note") for s in repeats)
        )
        if acknowledged:
            handled += 1
        else:
            criticals.append(
                f"{name}: '{repeats[0].get('selector')}' matches {repeats[0].get('count')} "
                f"elements with no note and testability_gap=false"
            )

    if ambiguous == 0:
        return DimensionResult(5, ["no strategy resolves to more than one element -- nothing to flag"])

    notes = [f"{handled}/{ambiguous} multi-match elements acknowledge the repetition"]
    return DimensionResult(_scale(handled, ambiguous), notes, criticals)


# ---------------------------------------------------------------------------
# 5. multi_strategy_coverage
# ---------------------------------------------------------------------------
def score_multi_strategy_coverage(element_map: dict, target: dict | None = None) -> DimensionResult:
    """Does each element carry a fallback that would actually work?

    Presence only. Unit 0 found 47 distinct or_chain formats across 20 traces --
    that is a missing spec, not a model defect, so format is deliberately not
    scored here. Writing the spec has to come before checking against it.
    """
    elements = element_map.get("elements") or []
    ok = 0
    notes: list[str] = []

    for el in elements:
        name = el.get("name", "<unnamed>")
        verified = [s for s in _strategies(el) if _count_is_measured(s)]
        if not el.get("or_chain"):
            notes.append(f"{name}: no or_chain")
        elif len(verified) >= 2:
            ok += 1
        else:
            notes.append(
                f"{name}: or_chain present but only {len(verified)} strategy with a measured "
                f"count -- the fallback was never run"
            )

    notes.insert(0, f"{ok}/{len(elements)} elements have a fallback that was actually verified")
    return DimensionResult(_scale(ok, len(elements)), notes)


SCORERS = {
    "semantic_primary_rate": score_semantic_primary_rate,
    "coverage_completeness": score_coverage_completeness,
    "strategy_validation": score_strategy_validation,
    "dynamic_content_flagging": score_dynamic_content_flagging,
    "multi_strategy_coverage": score_multi_strategy_coverage,
}


def score_deterministic(element_map: dict, target: dict | None = None) -> dict[str, DimensionResult]:
    """Run every code-scored dimension. Same 0-5 scale the LLM used, so these
    slot straight into the existing 35-point total."""
    return {name: fn(element_map, target) for name, fn in SCORERS.items()}


def flatten(
    results: dict[str, DimensionResult],
) -> tuple[dict[str, int], list[str], dict[str, list[str]]]:
    """(scores, critical_failures, notes-by-dimension) for the grader to merge."""
    scores = {k: r.score for k, r in results.items()}
    criticals = [f"[{k}] {c}" for k, r in results.items() for c in r.critical_failures]
    notes = {k: r.notes for k, r in results.items()}
    return scores, criticals, notes
