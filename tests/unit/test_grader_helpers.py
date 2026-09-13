import pytest

from agents.grader.grader_agent import _load_golden_case
from agents.grader.grading_tools import _captured, take_captured


def test_load_golden_case_finds_existing_case():
    case = _load_golden_case("explore-golden.json", "login")
    assert case["name"] == "login"
    assert case["expectations"]


def test_load_golden_case_raises_for_unknown_name():
    with pytest.raises(ValueError, match="No golden case named"):
        _load_golden_case("explore-golden.json", "does-not-exist")


def test_take_captured_raises_when_grader_never_called_submit():
    _captured.pop("explore", None)
    with pytest.raises(RuntimeError, match="never called submit_explore_grade"):
        take_captured("explore")


def test_take_captured_pops_and_returns_value():
    _captured["explore"] = {"dimensions": {}}
    result = take_captured("explore")
    assert result == {"dimensions": {}}
    assert "explore" not in _captured
