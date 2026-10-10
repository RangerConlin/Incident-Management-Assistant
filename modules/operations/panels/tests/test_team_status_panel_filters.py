import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from modules.operations.panels.team_status_panel import TeamStatusPanel


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _row(status: str, name: str) -> dict:
    return {
        "status": status,
        "name": name,
        "sortie": "",
        "team_type": "GT",
        "leader": "",
        "contact": "",
        "assignment": "",
        "location": "",
        "last_updated": None,
        "vehicle": "",
    }


@pytest.fixture
def panel(qt_app: QApplication) -> TeamStatusPanel:
    widget = TeamStatusPanel()
    try:
        yield widget
    finally:
        widget.close()


def test_kpi_strip_counts_by_status(panel: TeamStatusPanel) -> None:
    rows = [_row("assigned", "T-1"), _row("enroute", "T-2"), _row("available", "T-3"), _row("assigned", "T-4")]
    panel._render_rows(rows)

    assert panel._kpi_value_labels["total"].text() == "4"
    assert panel._kpi_value_labels["assigned"].text() == "2"
    assert panel._kpi_value_labels["enroute"].text() == "1"
    assert panel._kpi_value_labels["available"].text() == "1"


def test_status_chip_filters_visible_rows_without_changing_kpis(panel: TeamStatusPanel) -> None:
    rows = [_row("assigned", "T-1"), _row("enroute", "T-2"), _row("available", "T-3")]

    panel._render_rows(rows)
    assert panel.table.rowCount() == 3

    panel._status_chip = "enroute"
    panel._render_rows(rows)
    assert panel.table.rowCount() == 1
    # KPIs reflect the full data set, not the chip-filtered subset.
    assert panel._kpi_value_labels["total"].text() == "3"

    panel._status_chip = "all"
    panel._render_rows(rows)
    assert panel.table.rowCount() == 3


def test_needs_attention_chip_uses_alert_computation(panel: TeamStatusPanel) -> None:
    # "enroute" with no check-in timestamp is a timed status missing its
    # reference time, which compute_alert_kind treats as a warning (see
    # team_alerts.compute_alert_kind) -- so it counts as needing attention
    # even though its literal status string isn't one of the quick chips.
    rows = [_row("available", "T-1"), _row("enroute", "T-2")]

    panel._status_chip = "needs_attention"
    panel._render_rows(rows)

    assert panel.table.rowCount() == 1
    assert panel._kpi_value_labels["needs_attention"].text() == "1"
