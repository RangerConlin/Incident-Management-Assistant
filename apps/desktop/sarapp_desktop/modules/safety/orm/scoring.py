"""SPE (Severity x Probability x Exposure) hazard scoring."""

from __future__ import annotations

SEVERITY_RANGE = (1, 5)
PROBABILITY_RANGE = (1, 5)
EXPOSURE_RANGE = (1, 4)

# (score floor, degree, action) — highest floor the score meets or exceeds wins.
SPE_BANDS = (
    (80, "Very High", "Discontinue / Stop"),
    (60, "High", "Correct Immediately"),
    (40, "Substantial", "Correction Required"),
    (20, "Possible", "Attention Needed"),
    (1, "Slight", "Possibly Acceptable"),
)


def spe_score(severity: int, probability: int, exposure: int) -> int:
    return severity * probability * exposure


def spe_band(score: int) -> tuple[str, str]:
    """Return (degree, action) for a given SPE score."""
    for floor, degree, action in SPE_BANDS:
        if score >= floor:
            return degree, action
    return SPE_BANDS[-1][1], SPE_BANDS[-1][2]
