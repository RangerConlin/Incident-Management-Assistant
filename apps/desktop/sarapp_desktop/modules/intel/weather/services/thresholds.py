"""Go/No-Go operational threshold evaluation.

No such thresholds/config existed anywhere in this app before this module —
confirmed by codebase research (no Air Ops module, no go/no-go checklist, no
structured wind/visibility/ceiling limit fields). This is the single
comparison implementation shared by the Forecast tab's Air Ops column and
the Aviation tab's card/modal badges.

Rule: for each configured metric, worse-than-no-go wins immediately (any
single metric hitting no-go makes the whole reading no-go); otherwise
worse-than-marginal on any metric makes it marginal; otherwise go.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

Verdict = str  # "go" | "marginal" | "no_go"

DEFAULT_GROUND_THRESHOLDS: Dict[str, float] = {
    "wind_gust_marginal_mph": 20.0,
    "wind_gust_nogo_mph": 30.0,
    "visibility_marginal_mi": 3.0,
    "visibility_nogo_mi": 1.0,
    "ceiling_marginal_ft": 1500.0,
    "ceiling_nogo_ft": 500.0,
    "heat_index_marginal_f": 90.0,
    "heat_index_nogo_f": 103.0,
}

DEFAULT_AVIATION_THRESHOLDS: Dict[str, float] = {
    "wind_gust_marginal_kt": 15.0,
    "wind_gust_nogo_kt": 25.0,
    "visibility_marginal_sm": 3.0,
    "visibility_nogo_sm": 1.0,
    "ceiling_marginal_ft_agl": 1000.0,
    "ceiling_nogo_ft_agl": 300.0,
    "crosswind_marginal_kt": 15.0,
    "crosswind_nogo_kt": 25.0,
}


@dataclass(slots=True)
class MetricCheck:
    """One metric compared against its marginal/no-go boundary.

    `higher_is_worse=True` for things like wind gust/heat index (worse as the
    value climbs); `False` for things like visibility/ceiling (worse as the
    value drops).
    """

    name: str
    value: Optional[float]
    marginal: float
    nogo: float
    higher_is_worse: bool = True

    def verdict(self) -> Verdict:
        if self.value is None:
            return "go"
        if self.higher_is_worse:
            if self.value >= self.nogo:
                return "no_go"
            if self.value >= self.marginal:
                return "marginal"
            return "go"
        if self.value <= self.nogo:
            return "no_go"
        if self.value <= self.marginal:
            return "marginal"
        return "go"


_VERDICT_RANK = {"go": 0, "marginal": 1, "no_go": 2}


def _combine(verdicts: list[Verdict]) -> Verdict:
    if not verdicts:
        return "go"
    worst = max(verdicts, key=lambda v: _VERDICT_RANK[v])
    return worst


def evaluate_ground(reading: Dict[str, Any], thresholds: Optional[Dict[str, Any]] = None) -> Verdict:
    """Evaluate a normalized ground-ops reading (mph/mi/ft/°F) against thresholds."""
    t = {**DEFAULT_GROUND_THRESHOLDS, **(thresholds or {})}
    checks = [
        MetricCheck("wind_gust", reading.get("wind_gust_mph"), t["wind_gust_marginal_mph"], t["wind_gust_nogo_mph"]),
        MetricCheck(
            "visibility",
            reading.get("visibility_mi"),
            t["visibility_marginal_mi"],
            t["visibility_nogo_mi"],
            higher_is_worse=False,
        ),
        MetricCheck(
            "ceiling", reading.get("ceiling_ft"), t["ceiling_marginal_ft"], t["ceiling_nogo_ft"], higher_is_worse=False
        ),
        MetricCheck(
            "heat_index", reading.get("heat_index_f"), t["heat_index_marginal_f"], t["heat_index_nogo_f"]
        ),
    ]
    return _combine([c.verdict() for c in checks])


def evaluate_aviation(
    reading: Dict[str, Any],
    thresholds: Optional[Dict[str, Any]] = None,
    *,
    crosswind_kt: Optional[float] = None,
) -> Verdict:
    """Evaluate a normalized aviation reading (kt/sm/ft AGL) against thresholds."""
    t = {**DEFAULT_AVIATION_THRESHOLDS, **(thresholds or {})}
    checks = [
        MetricCheck(
            "wind_gust", reading.get("wind_gust_kt"), t["wind_gust_marginal_kt"], t["wind_gust_nogo_kt"]
        ),
        MetricCheck(
            "visibility",
            reading.get("visibility_sm"),
            t["visibility_marginal_sm"],
            t["visibility_nogo_sm"],
            higher_is_worse=False,
        ),
        MetricCheck(
            "ceiling",
            reading.get("ceiling_ft"),
            t["ceiling_marginal_ft_agl"],
            t["ceiling_nogo_ft_agl"],
            higher_is_worse=False,
        ),
    ]
    if crosswind_kt is not None:
        checks.append(
            MetricCheck("crosswind", crosswind_kt, t["crosswind_marginal_kt"], t["crosswind_nogo_kt"])
        )
    return _combine([c.verdict() for c in checks])


__all__ = [
    "Verdict",
    "MetricCheck",
    "DEFAULT_GROUND_THRESHOLDS",
    "DEFAULT_AVIATION_THRESHOLDS",
    "evaluate_ground",
    "evaluate_aviation",
]
