"""validate_explorer_output is the deterministic replacement for the
schema_compliance dimension the grader used to have an LLM judge. If this
regresses, malformed element-maps stop getting caught before they cost a
live grading run.
"""

import copy

from agents.shared.schemas import validate_explorer_output

VALID = {
    "page": "login",
    "url": "https://www.saucedemo.com/",
    "viewport": "1280x720",
    "crawled_at": "2026-08-27T00:00:00Z",
    "stats": {"total": 1, "with_primary": 1, "gaps": 0},
    "elements": [
        {
            "name": "usernameInput",
            "role": "textbox",
            "strategies": [
                {"type": "placeholder", "selector": "placeholder=Username", "count": 1, "confidence": 5, "note": None}
            ],
            "primary": {"type": "placeholder", "selector": "placeholder=Username", "count": 1, "confidence": 5, "note": None},
            "or_chain": None,
            "accessibility_node": {"role": "textbox", "name": "Username"},
            "testability_gap": False,
            "gap_note": None,
        }
    ],
}


def test_valid_element_map_has_no_errors():
    assert validate_explorer_output(copy.deepcopy(VALID)) == []


def test_missing_required_top_level_field():
    data = copy.deepcopy(VALID)
    del data["stats"]
    errors = validate_explorer_output(data)
    assert any("stats" in e for e in errors)


def test_primary_null_is_valid():
    data = copy.deepcopy(VALID)
    data["elements"][0]["primary"] = None
    assert validate_explorer_output(data) == []


def test_invalid_strategy_type_enum():
    data = copy.deepcopy(VALID)
    data["elements"][0]["strategies"][0]["type"] = "not-a-real-type"
    errors = validate_explorer_output(data)
    assert errors  # enum violation caught

def test_confidence_out_of_range():
    data = copy.deepcopy(VALID)
    data["elements"][0]["primary"]["confidence"] = 9
    errors = validate_explorer_output(data)
    assert errors


def test_missing_element_field():
    data = copy.deepcopy(VALID)
    del data["elements"][0]["testability_gap"]
    errors = validate_explorer_output(data)
    assert any("testability_gap" in e for e in errors)
