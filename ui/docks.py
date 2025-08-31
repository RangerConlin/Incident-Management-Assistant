from __future__ import annotations

from typing import Iterable

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
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


def create_team_status_dock(parent=None):
    w = QWidget(parent)
    layout = QVBoxLayout(w)
    table = _make_table(TEAM_HEADERS, TEAM_ROWS)
    layout.addWidget(table)
    dock = CDockWidget("Team Status")
    dock.setWidget(w)
    return dock


def create_task_status_dock(parent=None):
    w = QWidget(parent)
    layout = QVBoxLayout(w)
    table = _make_table(TASK_HEADERS, TASK_ROWS)
    layout.addWidget(table)
    dock = CDockWidget("Task Status")
    dock.setWidget(w)
    return dock

