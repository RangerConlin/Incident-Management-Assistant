"""Shared scaffolding helpers for the tabbed Liaison panels.

Kept separate from windows.py's board classes because these are layout
helpers (stat-card rows, filter sidebars, empty-state tables) reused across
several panels, not table-model logic.
"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QStandardItemModel

from utils.itemview_delegates import RowOutlineSelectionDelegate
from utils.styles import get_palette


def stat_card(title: str) -> tuple[QFrame, QLabel]:
    frame = QFrame()
    frame.setFrameShape(QFrame.StyledPanel)
    frame.setAttribute(Qt.WA_StyledBackground, True)
    frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    frame.setFixedHeight(72)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(6, 8, 6, 8)
    lay.setSpacing(2)
    count = QLabel("0")
    count.setStyleSheet("font-size:24px; font-weight:700; background:transparent;")
    count.setAlignment(Qt.AlignCenter)
    name = QLabel(title)
    name.setStyleSheet("font-size:11px; font-weight:600; background:transparent;")
    name.setAlignment(Qt.AlignCenter)
    name.setWordWrap(True)
    lay.addWidget(count)
    lay.addWidget(name)
    return frame, count


def tint_stat_card(frame: QFrame, count_label: QLabel, brushes: dict | None) -> None:
    if not brushes:
        frame.setStyleSheet("QFrame { border: 1px solid palette(mid); border-radius: 6px; }")
        return
    bg = brushes["bg"].color().name()
    fg = brushes["fg"].color().name()
    frame.setStyleSheet(f"QFrame {{ background-color: {bg}; border-radius: 6px; }}")
    count_label.setStyleSheet(f"font-size:24px; font-weight:700; background:transparent; color:{fg};")


def stat_row(titles: list[str]) -> tuple[QHBoxLayout, dict[str, tuple[QFrame, QLabel]]]:
    row = QHBoxLayout()
    row.setSpacing(10)
    cards: dict[str, tuple[QFrame, QLabel]] = {}
    for title in titles:
        card, label = stat_card(title)
        row.addWidget(card)
        cards[title] = (card, label)
    return row, cards


def filter_group(title: str) -> tuple[QGroupBox, QVBoxLayout]:
    box = QGroupBox(title)
    lay = QVBoxLayout(box)
    lay.setContentsMargins(8, 16, 8, 8)
    lay.setSpacing(6)
    return box, lay


def build_filter_sidebar(sections: list[tuple[str, list[str]]]) -> QWidget:
    """A left filter sidebar of checkbox groups, per the mockups.

    ``sections`` is a list of (group title, option labels). Purely visual —
    callers that back real filtering wire the checkboxes themselves.
    """
    sidebar = QWidget()
    sidebar.setFixedWidth(220)
    lay = QVBoxLayout(sidebar)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    search = QLineEdit(sidebar)
    search.setPlaceholderText("Search...")
    lay.addWidget(search)
    for title, options in sections:
        box, box_lay = filter_group(title)
        for option in options:
            box_lay.addWidget(QCheckBox(option, box))
        lay.addWidget(box)
    lay.addStretch(1)
    return sidebar


def build_table(headers: list[str]) -> tuple[QTableView, QStandardItemModel]:
    model = QStandardItemModel()
    model.setHorizontalHeaderLabels(headers)
    table = QTableView()
    table.setModel(model)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSortingEnabled(True)
    try:
        pal = get_palette()
        color = pal.get("ctrl_focus", pal.get("accent"))
        delegate = RowOutlineSelectionDelegate(table, color)
        table.setItemDelegate(delegate)
        table._row_outline_delegate = delegate  # keep alive
    except Exception:
        pass
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.Interactive)
    header.setStretchLastSection(True)
    return table, model


def detail_placeholder(text: str) -> QWidget:
    widget = QWidget()
    lay = QVBoxLayout(widget)
    label = QLabel(text)
    label.setWordWrap(True)
    label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    lay.addWidget(label)
    lay.addStretch(1)
    return widget


def action_bar(actions: list[str]) -> tuple[QHBoxLayout, dict[str, QPushButton]]:
    row = QHBoxLayout()
    row.setSpacing(4)
    buttons: dict[str, QPushButton] = {}
    for label in actions:
        btn = QPushButton(label)
        row.addWidget(btn)
        buttons[label] = btn
    return row, buttons
