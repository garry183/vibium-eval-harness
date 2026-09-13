"""Band boundaries are where judge noise turns into a discrete gate flip
(research flagged this: an unanchored summed rubric feeding a hard A/B gate
means a 1-point judge wobble near 26 or 32 changes the outcome). These pin
every boundary exactly so a future rescale doesn't silently leave a gap or
overlap in the 0-35 range.
"""

import pytest

from agents.shared.config import EXPLORE_GRADE_BANDS, band_for_score


@pytest.mark.parametrize(
    "score,expected_band",
    [
        (0, "F"), (10, "F"),
        (11, "D"), (17, "D"),
        (18, "C"), (25, "C"),
        (26, "B"), (31, "B"),
        (32, "A"), (35, "A"),
    ],
)
def test_band_boundaries(score, expected_band):
    assert band_for_score(score) == expected_band


def test_bands_cover_0_to_35_with_no_gaps_or_overlaps():
    covered = set()
    for lo, hi in EXPLORE_GRADE_BANDS.values():
        band_range = set(range(lo, hi + 1))
        assert not (covered & band_range), "band ranges overlap"
        covered |= band_range
    assert covered == set(range(0, 36))


def test_score_above_max_falls_back_to_f():
    # Defensive: band_for_score should never raise on unexpected input.
    assert band_for_score(999) == "F"
