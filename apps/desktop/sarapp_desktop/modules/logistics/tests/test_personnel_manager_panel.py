from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:  # pragma: no cover - import guard for environments without Qt libs
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    pytest.skip("PySide6 QtWidgets is unavailable", allow_module_level=True)

from modules.logistics.panels import personnel_manager_panel as panel_module
from modules.logistics.panels.personnel_manager_panel import LogisticsPersonnelManagerPanel
from utils import incident_context


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_personnel_manager_populates_roster(qt_app: QApplication, monkeypatch) -> None:
    incident_context.set_active_incident("logistics-personnel-panel-test")

    rows = [
        SimpleNamespace(
            person_record=17,
            person_id="CAP-17",
            name="Alex Rivera",
            role="Ground Team",
            team="Team 1",
            callsign="RIVER",
            phone="555-0100",
            ci_status="Assigned",
            updated_at="2026-10-13T12:30:00+00:00",
        )
    ]
    monkeypatch.setattr(panel_module, "fetch_roster", lambda filters: rows)

    panel = LogisticsPersonnelManagerPanel()
    assert panel._table.rowCount() == 1
    assert panel._table.item(0, 0).text() == "Alex Rivera"
    assert "1 personnel" in panel._summary.text()


def test_personnel_manager_quick_status_action(qt_app: QApplication, monkeypatch) -> None:
    incident_context.set_active_incident("logistics-personnel-panel-test")
    monkeypatch.setattr(panel_module, "fetch_roster", lambda filters: _rows())
    calls = []

    class _FakeApiClient:
        def patch(self, path, json):
            calls.append((path, json))
            return {"ok": True}

    monkeypatch.setattr(panel_module, "api_client", _FakeApiClient())

    panel = LogisticsPersonnelManagerPanel()
    panel._table.selectRow(0)
    panel._set_selected_status("Demobilized")

    assert calls == [
        (
            "/api/incidents/logistics-personnel-panel-test/checkin/17/status",
            {"status": "Demobilized"},
        )
    ]


def test_personnel_manager_history_dialog_loads_items(qt_app: QApplication, monkeypatch) -> None:
    incident_context.set_active_incident("logistics-personnel-panel-test")
    monkeypatch.setattr(panel_module, "fetch_roster", lambda filters: _rows())
    monkeypatch.setattr(
        panel_module,
        "list_history",
        lambda person_record: [
            SimpleNamespace(
                ts="2026-10-13T12:30:00+00:00",
                actor="pytest",
                event_type="STATUS_CHANGE",
                payload={"status": "Available"},
            )
        ],
    )
    monkeypatch.setattr(panel_module.QDialog, "exec", lambda self: 0)

    panel = LogisticsPersonnelManagerPanel()
    panel._table.selectRow(0)
    panel._show_selected_history()


def _rows():
    return [
        SimpleNamespace(
            person_record=17,
            person_id="CAP-17",
            name="Alex Rivera",
            role="Ground Team",
            team="Team 1",
            callsign="RIVER",
            phone="555-0100",
            ci_status="Assigned",
            updated_at="2026-10-13T12:30:00+00:00",
        )
    ]
