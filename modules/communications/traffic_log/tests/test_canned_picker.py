from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from modules.communications.traffic_log.ui.canned_picker import CannedCommPickerDialog
from modules.communications.traffic_log.ui.quick_entry import QuickEntryWidget


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_canned_picker_selects_entry():
    _ensure_app()
    rows = [
        {"id": 1, "title": "Test A", "category": "Ops", "message": "Alpha msg", "is_active": True},
        {"id": 2, "title": "Test B", "category": "Comms", "message": "Bravo msg", "is_active": True},
    ]
    with patch("modules.communications.traffic_log.ui.canned_picker._api") as mock_api:
        mock_api.return_value.get.return_value = rows
        dlg = CannedCommPickerDialog(None)
        dlg.table.selectRow(0)
        dlg._accept()
        assert dlg.selected_entry() is not None
        assert dlg.selected_entry()["title"] == "Test A"


def test_canned_picker_selection_maps_by_id_after_sort():
    _ensure_app()
    rows = [
        {"id": 2, "title": "Bravo", "category": "Ops", "message": "B msg", "is_active": True},
        {"id": 1, "title": "Alpha", "category": "Comms", "message": "A msg", "is_active": True},
        {"id": 3, "title": "Charlie", "category": "Log", "message": "C msg", "is_active": True},
    ]
    with patch("modules.communications.traffic_log.ui.canned_picker._api") as mock_api:
        mock_api.return_value.get.return_value = rows
        dlg = CannedCommPickerDialog(None)
        # Sort by Title ascending; first row should be Alpha (id=1)
        dlg.table.sortByColumn(0, Qt.AscendingOrder)
        dlg.table.selectRow(0)
        dlg._accept()
        sel = dlg.selected_entry()
        assert sel is not None
        assert int(sel.get("id")) == 1


def test_quick_entry_has_canned_button():
    """QuickEntryWidget — not CommunicationsLogWindow — owns the canned-entry
    button; the dashboard window dropped its embedded quick-entry form (see
    log_window.py's "Inline canned button exists in Quick Entry" comment) in
    favor of the separate QuickEntryPanel/quick_entry_window.py."""
    _ensure_app()
    widget = QuickEntryWidget()
    assert hasattr(widget, "canned_btn")
    assert "canned" in widget.canned_btn.text().lower()
