from __future__ import annotations

import pytest

from modules.safety.orm.scoring import spe_band, spe_score


def test_spe_score_is_multiplicative():
    assert spe_score(5, 5, 4) == 100
    assert spe_score(1, 1, 1) == 1
    assert spe_score(4, 3, 4) == 48


@pytest.mark.parametrize(
    "score,expected_degree,expected_action",
    [
        (100, "Very High", "Discontinue / Stop"),
        (80, "Very High", "Discontinue / Stop"),
        (79, "High", "Correct Immediately"),
        (60, "High", "Correct Immediately"),
        (59, "Substantial", "Correction Required"),
        (40, "Substantial", "Correction Required"),
        (39, "Possible", "Attention Needed"),
        (20, "Possible", "Attention Needed"),
        (19, "Slight", "Possibly Acceptable"),
        (1, "Slight", "Possibly Acceptable"),
    ],
)
def test_spe_band_boundaries(score, expected_degree, expected_action):
    degree, action = spe_band(score)
    assert degree == expected_degree
    assert action == expected_action
