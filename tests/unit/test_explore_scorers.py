"""Unit 2's scorers, tested in both directions.

Unit 0 named two behaviours worth protecting as regressions: a run that
correctly refused to fabricate, and all 8 runs correctly ruling out `text=` on
an <input type=submit>. A scorer that only ever fires on bad input is untested
in the passing direction, so every dimension here gets a clean case and a
dirty one.
"""

from __future__ import annotations

import pytest

from agents.grader.explore_scorers import (
    CODE_DIMENSIONS,
    flatten,
    score_coverage_completeness,
    score_deterministic,
    score_dynamic_content_flagging,
    score_multi_strategy_coverage,
    score_semantic_primary_rate,
    score_strategy_validation,
)


def strat(type_="placeholder", selector="placeholder=Username", count=1, confidence=5, note=None):
    return {"type": type_, "selector": selector, "count": count, "confidence": confidence, "note": note}


_UNSET = object()


def element(name="usernameInput", strategies=None, primary=_UNSET, or_chain="a || b", **kw):
    strategies = strategies if strategies is not None else [strat()]
    el = {
        "name": name,
        "role": "textbox",
        "strategies": strategies,
        "primary": (strategies[0] if strategies else None) if primary is _UNSET else primary,
        "or_chain": or_chain,
        "accessibility_node": {"role": "textbox", "name": "Username"},
        "testability_gap": False,
        "gap_note": None,
    }
    el.update(kw)
    return el


def emap(*elements):
    return {"page": "login", "url": "/", "viewport": "1280x720", "crawled_at": "z",
            "stats": {"total": len(elements), "with_primary": len(elements), "gaps": 0},
            "elements": list(elements)}


TARGET = {
    "elements": [
        {
            "name": "usernameInput",
            "correct_primary": ["placeholder=Username"],
            "acceptable_fallback": ["#user-name", '[data-test="username"]'],
        },
        {
            "name": "loginButton",
            "correct_primary": ["role=button,label=Login"],
            "acceptable_fallback": ["#login-button"],
        },
    ]
}


# --- semantic_primary_rate -------------------------------------------------

def test_semantic_primary_all_semantic_scores_5():
    r = score_semantic_primary_rate(emap(element(), element(name="b")))
    assert r.score == 5
    assert r.critical_failures == []


def test_semantic_primary_css_primary_is_critical():
    css = strat("css", ".form_input")
    r = score_semantic_primary_rate(emap(element(strategies=[css], primary=css)))
    assert r.score == 0
    assert "non-semantic" in r.critical_failures[0]


def test_semantic_primary_missing_primary_is_critical():
    r = score_semantic_primary_rate(emap(element(primary=None)))
    assert r.score == 0
    assert "no primary strategy" in r.critical_failures[0]


# --- coverage_completeness -------------------------------------------------

def test_coverage_matches_on_selector_not_name():
    """The explorer's element names are invented; the answer key's selectors
    are not. A map that renames everything still counts as covering."""
    m = emap(
        element(name="theUserBox"),
        element(name="theSubmit", strategies=[strat("role", "role=button,label=Login")]),
    )
    r = score_coverage_completeness(m, TARGET)
    assert r.score == 5
    assert r.critical_failures == []


def test_coverage_missing_element_is_critical():
    r = score_coverage_completeness(emap(element()), TARGET)
    assert r.score == 3  # 1 of 2 -> 2.5 -> 3
    assert r.critical_failures == ["missing from element-map: loginButton"]


def test_coverage_without_target_is_unscoreable_not_zero_quietly():
    r = score_coverage_completeness(emap(element()), None)
    assert r.score == 0
    assert "no target supplied" in r.notes[0]


def test_coverage_extra_elements_are_noted_not_penalised():
    m = emap(element(), element(name="theSubmit", strategies=[strat("role", "role=button,label=Login")]),
             element(name="botColumn", strategies=[strat("text", "text=Swag Labs")]))
    r = score_coverage_completeness(m, TARGET)
    assert r.score == 5
    assert any("not in the answer key" in n for n in r.notes)


# --- strategy_validation ---------------------------------------------------

def test_strategy_validation_clean_map_scores_5():
    r = score_strategy_validation(emap(element(strategies=[strat(), strat("css", "#user-name", count=1, confidence=3)])))
    assert r.score == 5
    assert r.critical_failures == []


def test_null_count_is_an_unexecuted_assertion():
    s = strat("css", '[data-test="username"]', count=None, confidence=3, note="Not verified via vibium")
    r = score_strategy_validation(emap(element(strategies=[strat(), s])))
    assert any("never executed" in n for n in r.notes)
    assert any("confidence 3" in c for c in r.critical_failures)


def test_zero_count_from_a_timeout_is_not_treated_as_evidence():
    """Unit 0 cluster 3: find_all raises on no-match, so a recorded 0 was
    inferred from an exception. It must not read as a measurement."""
    s = strat("label", "role=textbox,label=Username", count=0, confidence=1,
              note="Timed out / no match. Accessible name derived from placeholder.")
    r = score_strategy_validation(emap(element(strategies=[strat(), s])))
    assert any("inferred, not measured" in n for n in r.notes)
    # confidence 1 means the explorer already distrusted it -- note, don't gate
    assert r.critical_failures == []


def test_zero_count_with_no_note_has_no_provenance():
    s = strat("label", "label=Username", count=0, confidence=4, note=None)
    r = score_strategy_validation(emap(element(strategies=[strat(), s])))
    assert any("no provenance note" in n for n in r.notes)
    assert any("unverified" in c for c in r.critical_failures)


def test_primary_not_among_strategies_is_critical():
    ghost = strat("role", "role=textbox")
    r = score_strategy_validation(emap(element(strategies=[strat()], primary=ghost)))
    assert any("not among the listed strategies" in c for c in r.critical_failures)


def test_ambiguous_primary_is_critical():
    amb = strat("role", "role=textbox", count=2)
    r = score_strategy_validation(emap(element(strategies=[amb], primary=amb)))
    assert any("ambiguous (count=2)" in c for c in r.critical_failures)


def test_primary_resolving_to_nothing_is_critical():
    dead = strat("text", "text=Login", count=0, confidence=1, note="no match")
    r = score_strategy_validation(emap(element(strategies=[dead], primary=dead)))
    assert any("resolves to nothing" in c for c in r.critical_failures)


# --- dynamic_content_flagging ----------------------------------------------

def test_no_multi_match_means_nothing_to_flag():
    r = score_dynamic_content_flagging(emap(element()))
    assert r.score == 5
    assert "nothing to flag" in r.notes[0]


def test_acknowledged_repetition_scores_full():
    many = strat("role", "role=button,label=Add to cart", count=6, note="one per product card")
    r = score_dynamic_content_flagging(emap(element(name="addToCart", strategies=[many], primary=many)))
    assert r.score == 5
    assert r.critical_failures == []


def test_unacknowledged_repetition_is_critical():
    many = strat("role", "role=button,label=Add to cart", count=6, note=None)
    r = score_dynamic_content_flagging(emap(element(name="addToCart", strategies=[many], primary=many)))
    assert r.score == 0
    assert "matches 6 elements" in r.critical_failures[0]


# --- multi_strategy_coverage -----------------------------------------------

def test_two_verified_strategies_plus_chain_scores_5():
    r = score_multi_strategy_coverage(emap(element(strategies=[strat(), strat("css", "#user-name")])))
    assert r.score == 5


def test_or_chain_whose_fallback_was_never_run_does_not_count():
    unrun = strat("css", '[data-test="username"]', count=None, confidence=3)
    r = score_multi_strategy_coverage(emap(element(strategies=[strat(), unrun])))
    assert r.score == 0
    assert any("never run" in n for n in r.notes)


def test_missing_or_chain_is_noted():
    r = score_multi_strategy_coverage(emap(element(or_chain=None)))
    assert r.score == 0
    assert any("no or_chain" in n for n in r.notes)


def test_or_chain_format_is_deliberately_not_scored():
    """47 formats across 20 traces is a missing spec, not a model defect. Until
    the spec exists, any format is accepted."""
    weird = element(strategies=[strat(), strat("css", "#user-name")], or_chain="ANY NONSENSE >>> HERE")
    assert score_multi_strategy_coverage(emap(weird)).score == 5


# --- aggregate -------------------------------------------------------------

def test_score_deterministic_covers_exactly_the_code_dimensions():
    results = score_deterministic(emap(element()), TARGET)
    assert sorted(results) == sorted(CODE_DIMENSIONS)
    assert all(0 <= r.score <= 5 for r in results.values())


def test_flatten_tags_criticals_with_their_dimension():
    css = strat("css", ".form_input")
    scores, criticals, notes = flatten(score_deterministic(emap(element(strategies=[css], primary=css)), TARGET))
    assert set(scores) == set(CODE_DIMENSIONS)
    assert any(c.startswith("[semantic_primary_rate]") for c in criticals)
    assert set(notes) == set(CODE_DIMENSIONS)


@pytest.mark.parametrize("dim", CODE_DIMENSIONS)
def test_every_code_dimension_is_deterministic(dim):
    m = emap(element(), element(name="loginButton", strategies=[strat("role", "role=button,label=Login")]))
    first = score_deterministic(m, TARGET)[dim].score
    assert all(score_deterministic(m, TARGET)[dim].score == first for _ in range(5))
