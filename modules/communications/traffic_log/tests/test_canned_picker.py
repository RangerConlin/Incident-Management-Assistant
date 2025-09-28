from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import QApplication

from modules.communications.traffic_log.ui.canned_picker import CannedCommPickerDialog
from modules.communications.traffic_log.ui.log_window import CommunicationsLogWindow


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _FakeBridge:
    def __init__(self, rows: List[Dict[str, Any]]):
        self._rows = rows

    def listCannedCommEntries(self, searchText: str = "") -> List[Dict[str, Any]]:  # noqa: N802
        if not searchText:
            return list(self._rows)
        s = searchText.strip().lower()
        return [r for r in self._rows if s in (r.get("title", "") or "").lower()]


def test_canned_picker_selects_entry():
    _ensure_app()
    rows = [
        {"id": 1, "title": "Test A", "category": "Ops", "message": "Alpha msg", "is_active": True},
        {"id": 2, "title": "Test B", "category": "Comms", "message": "Bravo msg", "is_active": True},
    ]
    dlg = CannedCommPickerDialog(None, catalog_bridge=_FakeBridge(rows))
    # select first row
    dlg.table.selectRow(0)
    assert dlg.selected_entry() is not None
    assert dlg.selected_entry()["title"] == "Test A"


def test_canned_picker_selection_maps_by_id_after_sort():
    _ensure_app()
    rows = [
        {"id": 2, "title": "Bravo", "category": "Ops", "message": "B msg", "is_active": True},
        {"id": 1, "title": "Alpha", "category": "Comms", "message": "A msg", "is_active": True},
        {"id": 3, "title": "Charlie", "category": "Log", "message": "C msg", "is_active": True},
    ]
    dlg = CannedCommPickerDialog(None, catalog_bridge=_FakeBridge(rows))
    # Sort by Title ascending; first row should be Alpha (id=1)
    dlg.table.sortByColumn(0, 0)
    dlg.table.selectRow(0)
    sel = dlg.selected_entry()
    assert sel is not None
    assert int(sel.get("id")) == 1


class _FakeService:
    def list_channels(self) -> list[dict]:
        return []

    def last_used_resource(self) -> Optional[int]:
        return None

    def list_contact_entities(self) -> list[dict]:
        return []

    def list_filter_presets(self, user_id: Optional[str] = None) -> list:
        return []

    def list_entries(self, query=None) -> list:
        return []


def test_quick_entry_has_canned_button():
    _ensure_app()
    win = CommunicationsLogWindow(_FakeService())
    assert hasattr(win, "quick_entry")
    assert hasattr(win.quick_entry, "canned_button")
    assert "canned" in win.quick_entry.canned_button.text().lower()
