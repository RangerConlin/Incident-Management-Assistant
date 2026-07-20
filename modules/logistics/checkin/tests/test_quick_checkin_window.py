from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from modules.logistics.checkin.panels.CheckInPanel import CheckInPanel
from modules.logistics.checkin.widgets import ICS211CheckInWindow
from modules.logistics.checkin.widgets.checkin_window import QuickCheckInWindow
from modules.logistics.windows import get_quick_checkin_panel


class _StubService:
    def __init__(self) -> None:
        self.records = [
            {
                "id": 405021,
                "person_id": "CAP-405021",
                "name": "Alex Scanner",
                "organization": "CAP",
                "phone": "555-0100",
                "role": "Ground",
                "status": "Pending",
                "_checked_in": False,
            }
        ]
        self.calls: list[tuple[str, Any]] = []

    def search_master_records(self, entity_type: str, query: str) -> list[dict[str, Any]]:
        self.calls.append(("search", entity_type, query))
        return list(self.records)

    def set_planning_status(self, person_id: str, status: str) -> dict[str, Any]:
        self.calls.append(("planning", person_id, status))
        return {"status": status}

    def transition_to_checked_in(self, person_id: str) -> dict[str, Any]:
        self.calls.append(("checked_in", person_id))
        return {"status": "Checked In", "_checked_in": True}

    def check_in(self, entity_type: str, person_id: str, overrides: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("check_in", entity_type, person_id, overrides))
        return {"status": overrides.get("status"), "_checked_in": overrides.get("status") == "Checked In"}


@pytest.fixture
def qt_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_checkin_panel_embeds_full_ics211_window(qt_app: QApplication) -> None:
    panel = CheckInPanel()
    assert isinstance(panel.window, ICS211CheckInWindow)


def test_quick_window_lookup_and_expected_status(qt_app: QApplication) -> None:
    service = _StubService()
    window = QuickCheckInWindow(checkin_service=service)

    window._entry.setText("405021")
    window.lookup_record()

    assert "Alex Scanner" in window._display.toPlainText()

    window.apply_status("Expected")

    assert ("search", "personnel", "405021") in service.calls
    assert ("planning", "405021", "Expected") in service.calls
    assert "Expected recorded." in window._display.toPlainText()


def test_quick_window_checked_in_action_uses_transition(qt_app: QApplication) -> None:
    service = _StubService()
    window = QuickCheckInWindow(checkin_service=service)

    window._entry.setText("CAP-405021")
    window.lookup_record()
    window.apply_status("Checked In")

    assert ("checked_in", "405021") in service.calls
    assert "Checked In recorded." in window._display.toPlainText()


def test_quick_window_checkout_action_sets_demobilized(qt_app: QApplication) -> None:
    service = _StubService()
    window = QuickCheckInWindow(checkin_service=service)

    window._entry.setText("405021")
    window.lookup_record()
    window.apply_status("Demobilized")

    assert ("planning", "405021", "Demobilized") in service.calls
    assert "Demobilized recorded." in window._display.toPlainText()
    assert "Checked In: No" in window._display.toPlainText()


def test_get_quick_checkin_panel_returns_quick_window(qt_app: QApplication) -> None:
    panel = get_quick_checkin_panel()
    assert isinstance(panel, QuickCheckInWindow)
