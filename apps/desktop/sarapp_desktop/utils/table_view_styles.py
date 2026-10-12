from __future__ import annotations

from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView

from utils.itemview_delegates import RowOutlineSelectionDelegate
from utils.styles import get_palette


def apply_statusboard_table_behavior(
    table: QTableView,
    *,
    stretch_last_section: bool = False,
    movable_sections: bool = True,
) -> None:
    """Apply the same baseline table behavior used by the status boards."""

    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setStyleSheet("QTableView { selection-background-color: transparent; }")

    header = table.horizontalHeader()
    header.setSectionsMovable(movable_sections)
    header.setStretchLastSection(stretch_last_section)
    col_count = table.model().columnCount() if table.model() else 0
    for idx in range(col_count):
        header.setSectionResizeMode(idx, QHeaderView.Interactive)

    try:
        pal = get_palette()
        color = pal.get("ctrl_focus", pal.get("accent"))
        delegate = RowOutlineSelectionDelegate(table, color)
        table.setItemDelegate(delegate)
        table._row_outline_delegate = delegate  # type: ignore[attr-defined]
    except Exception:
        pass
