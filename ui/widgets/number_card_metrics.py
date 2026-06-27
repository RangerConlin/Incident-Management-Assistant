"""Pre-defined metric definitions for NumberCardWidget.

Each NumberCardMetric defines a data source (MongoDB collection + filter logic)
that the NumberCardWidget uses to display a live count. Metrics are the "default
selections" users can choose from in the configuration dialog, and they can
customize label, colors, thresholds, and other logic on top of these.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ui.widgets.base import Size


# ── types ───────────────────────────────────────────────────────────────────

@dataclass
class ThresholdRule:
    """A conditional color rule applied when the value meets the operator.

    Rules are evaluated in order; the first match wins. If no rule matches,
    the card's default colors are used.
    """
    operator: str          # one of >=  <=  ==  >  <
    value: int
    fill_color: str        # CSS hex color for card background
    border_color: str      # CSS hex color for card border
    text_color: str        # CSS hex color for the number text
    label: str = ""        # optional human-readable name shown in the config UI

    def evaluate(self, current: int) -> bool:
        try:
            return {
                ">=": current >= self.value,
                "<=": current <= self.value,
                "==": current == self.value,
                ">":  current > self.value,
                "<":  current < self.value,
            }[self.operator]
        except KeyError:
            return False


@dataclass
class NumberCardMetric:
    """Describes one metric type that a NumberCardWidget can display.

    Subclass or instantiate directly with a ``value_fn`` that extracts an
    integer from a list of documents retrieved from IncidentCache.
    """
    id: str
    label: str
    collection: str                          # IncidentCache collection name
    default_color: str                       # CSS hex for number text
    default_fill: str                        # CSS hex for card background
    default_size: Size = field(default_factory=lambda: Size(3, 1))
    value_fn: Callable[[List[Dict[str, Any]]], int] = field(default=lambda docs: len(docs))
    default_thresholds: List[ThresholdRule] = field(default_factory=list)
    target_value: int = 0                    # for optional progress display
    view_action: Optional[str] = None        # optional "View more" route


# ── helper extractors ───────────────────────────────────────────────────────

def _count_where(*, status_field: str = "status", values: set[str]) -> Callable[[List[Dict[str, Any]]], int]:
    """Return a value_fn that counts docs whose *status_field* is in *values*."""
    def _extract(docs: List[Dict[str, Any]]) -> int:
        return sum(1 for d in docs if str(d.get(status_field, "")).lower() in values)
    return _extract


def _count_where_not(*, status_field: str = "status", values: set[str]) -> Callable[[List[Dict[str, Any]]], int]:
    """Return a value_fn that counts docs whose *status_field* is NOT in *values*."""
    def _extract(docs: List[Dict[str, Any]]) -> int:
        return sum(1 for d in docs if str(d.get(status_field, "")).lower() not in values)
    return _extract


# ── metric catalog ──────────────────────────────────────────────────────────

METRICS: Dict[str, NumberCardMetric] = {}

def _register(m: NumberCardMetric) -> NumberCardMetric:
    METRICS[m.id] = m
    return m


def get_metric(metric_id: str) -> Optional[NumberCardMetric]:
    return METRICS.get(metric_id)


def list_metrics() -> List[NumberCardMetric]:
    return sorted(METRICS.values(), key=lambda m: m.label.lower())


# ── Team metrics ────────────────────────────────────────────────────────────

_register(NumberCardMetric(
    id="teams_available",
    label="Available Teams",
    collection="teams",
    default_color="#4caf50",
    default_fill="#1a2a1a",
    value_fn=_count_where(values={"staging", "available"}),
    default_thresholds=[
        ThresholdRule("==", 0, fill_color="#1a1a1a", border_color="#555555",
                       text_color="#888888", label="No teams"),
    ],
    view_action="operations.teams",
))

_register(NumberCardMetric(
    id="teams_field",
    label="Teams in Field",
    collection="teams",
    default_color="#2196f3",
    default_fill="#1a2332",
    value_fn=_count_where(values={"enroute", "arrival", "returning", "returning to base"}),
    default_thresholds=[
        ThresholdRule("==", 0, fill_color="#1a1a1a", border_color="#555555",
                       text_color="#888888", label="None deployed"),
    ],
    view_action="operations.teams",
))

# ── Task metrics ────────────────────────────────────────────────────────────

_register(NumberCardMetric(
    id="tasks_pending",
    label="Pending Tasks",
    collection="tasks",
    default_color="#ff9800",
    default_fill="#2a2210",
    value_fn=_count_where_not(values={"completed", "cancelled"}),
    default_thresholds=[
        ThresholdRule("==", 0, fill_color="#1a2a1a", border_color="#4caf50",
                       text_color="#4caf50", label="All tasks complete!"),
        ThresholdRule(">=", 10, fill_color="#2a1818", border_color="#f44336",
                       text_color="#f44336", label="Heavy workload"),
    ],
    view_action="operations.tasks",
))

_register(NumberCardMetric(
    id="tasks_completed",
    label="Tasks Complete",
    collection="tasks",
    default_color="#4caf50",
    default_fill="#1a2a1a",
    value_fn=_count_where(values={"completed"}),
    default_thresholds=[
        ThresholdRule("==", 0, fill_color="#1a1a1a", border_color="#555555",
                       text_color="#888888", label="No completed tasks"),
    ],
    view_action="operations.tasks",
))

# ── Personnel / Check-in ────────────────────────────────────────────────────

_register(NumberCardMetric(
    id="personnel_in",
    label="Personnel In",
    collection="checkin",
    default_color="#2196f3",
    default_fill="#1a2332",
    value_fn=_count_where(values={"checked_in", "active"}),
    default_thresholds=[
        ThresholdRule("==", 0, fill_color="#2a1818", border_color="#f44336",
                       text_color="#f44336", label="No personnel checked in"),
    ],
    view_action="personnel.roster",
))

# ── Resource requests ───────────────────────────────────────────────────────

_register(NumberCardMetric(
    id="requests_open",
    label="Open Requests",
    collection="requests",
    default_color="#d29922",
    default_fill="#2a2210",
    value_fn=_count_where(values={"submitted", "reviewed", "approved"}),
    default_thresholds=[
        ThresholdRule("==", 0, fill_color="#1a2a1a", border_color="#4caf50",
                       text_color="#4caf50", label="No open requests"),
        ThresholdRule(">=", 5, fill_color="#2a1818", border_color="#f44336",
                       text_color="#f44336", label="Backlog growing"),
    ],
    view_action="logistics.requests",
))

# ── Safety / Alerts ─────────────────────────────────────────────────────────

_register(NumberCardMetric(
    id="alerts_active",
    label="Active Alerts",
    collection="safety",
    default_color="#f44336",
    default_fill="#2a1818",
    value_fn=_count_where(values={"open", "active", "critical"}),
    default_thresholds=[
        ThresholdRule("==", 0, fill_color="#1a2a1a", border_color="#4caf50",
                       text_color="#4caf50", label="All clear"),
        ThresholdRule(">=", 3, fill_color="#3a1515", border_color="#ff1744",
                       text_color="#ff1744", label="Multiple active alerts"),
    ],
    view_action="safety.dashboard",
))

# ── Equipment ───────────────────────────────────────────────────────────────

_register(NumberCardMetric(
    id="equipment_out",
    label="Equipment Out",
    collection="equipment",
    default_color="#9c27b0",
    default_fill="#241030",
    value_fn=_count_where(values={"checked_out", "in_use", "assigned"}),
    default_thresholds=[
        ThresholdRule("==", 0, fill_color="#1a1a1a", border_color="#555555",
                       text_color="#888888", label="All checked in"),
    ],
    view_action="logistics.equipment",
))
