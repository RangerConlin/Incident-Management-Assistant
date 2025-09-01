from __future__ import annotations

from typing import Iterable

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QMenu
from PySide6.QtCore import Qt
from styles import TEAM_STATUS_COLORS, TASK_STATUS_COLORS
from PySide6QtAds import CDockWidget

from data.sample_data import (
    TEAM_HEADERS,
    TEAM_ROWS,
    TASK_HEADERS,
    TASK_ROWS,
)


def _make_table(headers: Iterable[str], rows: Iterable[Iterable[object]]) -> QTableWidget:
    table = QTableWidget()
    headers = list(headers)
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    for r, row in enumerate(rows):
        table.insertRow(r)
        for c, value in enumerate(row):
            item = QTableWidgetItem(str(value))
            table.setItem(r, c, item)
    return table


def _apply_row_colors(table: QTableWidget, status_col: int, palette: dict[str, dict[str, object]]):
    try:
        rows = table.rowCount()
        for r in range(rows):
            item = table.item(r, status_col)
            if not item:
                continue
            status = (item.text() or "").strip().lower()
            style = palette.get(status)
            if not style:
                continue
            for c in range(table.columnCount()):
                cell = table.item(r, c)
                if cell:
                    cell.setBackground(style["bg"])  # QBrush
                    cell.setForeground(style["fg"])  # QBrush
    except Exception:
        pass

def _on_status_changed(table: QTableWidget, status_col: int, palette: dict[str, dict[str, object]]):
    def handler(item: QTableWidgetItem):
        try:
            if item.column() != status_col:
                return
            r = item.row()
            status = (item.text() or "").strip().lower()
            style = palette.get(status)
            if not style:
                return
            for c in range(table.columnCount()):
                cell = table.item(r, c)
                if cell:
                    cell.setBackground(style["bg"])  # QBrush
                    cell.setForeground(style["fg"])  # QBrush
        except Exception:
            pass
    return handler


def _attach_status_context_menu(table: QTableWidget, status_col: int, palette: dict[str, dict[str, object]], *,
                                on_view_detail=None):
    table.setContextMenuPolicy(Qt.CustomContextMenu)

    def open_menu(pos):
        index = table.indexAt(pos)
        row = index.row()
        if row < 0:
            return

        menu = QMenu(table)
        if on_view_detail:
            menu.addAction("View Detail", lambda: on_view_detail(row))
            menu.addSeparator()

        # Flat list of statuses from the palette
        for status in palette.keys():
            # capture status in default arg
            menu.addAction(status.title(), lambda s=status: _set_status(row, s))

        menu.exec(table.viewport().mapToGlobal(pos))

    def _set_status(row: int, new_status: str):
        # Update cell text and re-apply row colors
        item = table.item(row, status_col)
        if not item:
            item = QTableWidgetItem("")
            table.setItem(row, status_col, item)
        item.setText(new_status.title())
        # emit triggers itemChanged handler to recolor

    table.customContextMenuRequested.connect(open_menu)


def create_team_status_dock(parent=None):
    w = QWidget(parent)
    layout = QVBoxLayout(w)
    table = _make_table(TEAM_HEADERS, TEAM_ROWS)
    layout.addWidget(table)
    # Color rows by team status
    try:
        headers = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
        status_idx = headers.index("Status") if "Status" in headers else 4
        _apply_row_colors(table, status_idx, TEAM_STATUS_COLORS)
        table.itemChanged.connect(_on_status_changed(table, status_idx, TEAM_STATUS_COLORS))
        _attach_status_context_menu(
            table,
            status_idx,
            TEAM_STATUS_COLORS,
            on_view_detail=lambda r: print(f"[Team] View detail row={r}"),
        )
    except Exception:
        pass

    dock = CDockWidget("Team Status")
    dock.setWidget(w)
    return dock


def create_task_status_dock(parent=None):
    w = QWidget(parent)
    layout = QVBoxLayout(w)
    table = _make_table(TASK_HEADERS, TASK_ROWS)
    layout.addWidget(table)
    # Color rows by task status
    try:
        headers = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
        status_idx = headers.index("Status") if "Status" in headers else 2
        _apply_row_colors(table, status_idx, TASK_STATUS_COLORS)
        table.itemChanged.connect(_on_status_changed(table, status_idx, TASK_STATUS_COLORS))
        _attach_status_context_menu(
            table,
            status_idx,
            TASK_STATUS_COLORS,
            on_view_detail=lambda r: print(f"[Task] View detail row={r}"),
        )
    except Exception:
        pass

    dock = CDockWidget("Task Status")
    dock.setWidget(w)
    return dock

