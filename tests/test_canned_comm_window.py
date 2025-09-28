from __future__ import annotations

from typing import Any, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from panels.canned_comm_entries_window import CannedCommEntriesWindow


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _FakeBridge:
    def __init__(self, rows: List[Dict[str, Any]]):
        self._rows = rows

    def listCannedCommEntries(self, _text: str = "") -> List[Dict[str, Any]]:  # noqa: N802
        return list(self._rows)

    def createCannedCommEntry(self, data: Dict[str, Any]) -> int:  # noqa: N802
        return 0

    def updateCannedCommEntry(self, id_value: int, data: Dict[str, Any]) -> bool:  # noqa: N802
        return True

    def deleteCannedCommEntry(self, id_value: int) -> bool:  # noqa: N802
        return True


def test_id_column_hidden_and_selection_maps_correctly():
    _ensure_app()
    rows = [
        {"id": 2, "title": "Bravo", "category": "Ops", "message": "B msg", "is_active": True},
        {"id": 1, "title": "Alpha", "category": "Comms", "message": "A msg", "is_active": True},
        {"id": 3, "title": "Charlie", "category": "Log", "message": "C msg", "is_active": True},
    ]
    win = CannedCommEntriesWindow(catalog_bridge=_FakeBridge(rows))
    # ID column is hidden
    assert win.table.isColumnHidden(0)

    # Sort by Title ascending and select first row
    win.table.sortByColumn(1, Qt.AscendingOrder)
    win.table.selectRow(0)
    selected = win.current_entry()
    assert selected is not None
    # After sort, first by title should be Alpha (id=1)
    assert int(selected.get("id")) == 1

