"""Search Assignment Planner / Search Task Planner panel (SAR Toolkit).

Lists existing search tasks as a join of general Operations task fields
(team/resource via `assignment`/`title`, `status`) with the search-specific
fields held in `search_task_details`. Operations remains the sole owner of
the task/assignment record — see
modules/sartoolkit/data/search_task_repository.py for the publish flow and
the ownership decision writeup.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.sartoolkit.data import search_task_repository
from modules.sartoolkit.panels.search_task_dialog import SearchTaskDialog
from utils.table_view_styles import apply_statusboard_table_behavior
from utils.styles import get_palette, subscribe_theme, task_status_colors

_COLUMNS = [
    "Task ID",
    "Title",
    "Status",
    "Segment",
    "Search Method",
    "Track Spacing",
    "Team Leader",
    "Radio Ch.",
    "Departure",
    "Due Back",
]


class SearchTaskPlannerPanel(QWidget):
    panel_title = "Search Assignment Planner"

    def __init__(self, incident_id: object | None = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._incident_id = str(incident_id) if incident_id else None
        self._rows: list[dict] = []
        self._build_ui()
        subscribe_theme(self, lambda *_: self._repaint_rows())
        self.reload()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        header = QHBoxLayout()
        title = QLabel(self.panel_title)
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch(1)

        self._btn_new = QPushButton("+ New Task")
        self._btn_new.clicked.connect(self._on_new_task)
        header.addWidget(self._btn_new)

        self._btn_refresh = QPushButton("Refresh")
        self._btn_refresh.clicked.connect(self.reload)
        header.addWidget(self._btn_refresh)

        root.addLayout(header)

        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        apply_statusboard_table_behavior(self._table, stretch_last_section=True)
        root.addWidget(self._table, 1)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"color:{get_palette().get('fg_muted').name()};")
        root.addWidget(self._status_label)

    def reload(self) -> None:
        try:
            tasks = search_task_repository.list_operations_tasks()
            details = search_task_repository.list_search_task_details(self._incident_id)
        except Exception as exc:
            QMessageBox.critical(self, "Search Assignment Planner", f"Failed to load search tasks:\n{exc}")
            tasks, details = [], []

        details_by_task: dict[int, object] = {}
        for d in details:
            if d.task_id is not None:
                details_by_task[int(d.task_id)] = d

        segments_by_id = {}
        try:
            from modules.sartoolkit.data import segments_repository

            for seg in segments_repository.list_segments(self._incident_id):
                segments_by_id[seg.segment_id] = seg.name
        except Exception:
            pass

        self._rows = []
        for task in tasks:
            task_int_id = task.get("int_id")
            detail = details_by_task.get(int(task_int_id)) if task_int_id is not None else None
            if detail is None:
                # Only show tasks that are actually search tasks (have a linked detail)
                continue
            self._rows.append(
                {
                    "task_int_id": task_int_id,
                    "title": task.get("title", ""),
                    "status": task.get("status", ""),
                    "segment_name": segments_by_id.get(detail.segment_id, detail.segment_id or ""),
                    "search_method": detail.search_method,
                    "track_spacing": detail.track_spacing,
                    "team_leader": detail.team_leader,
                    "radio_channel": detail.radio_channel,
                    "departure_time": detail.departure_time or "",
                    "due_back_time": detail.due_back_time or "",
                }
            )
        self._status_label.setText(f"{len(self._rows)} search task(s)")
        self._render_table()

    def _render_table(self) -> None:
        self._table.setRowCount(len(self._rows))
        for row, data in enumerate(self._rows):
            values = [
                str(data["task_int_id"]),
                data["title"],
                data["status"],
                data["segment_name"],
                data["search_method"],
                data["track_spacing"],
                data["team_leader"],
                data["radio_channel"],
                data["departure_time"],
                data["due_back_time"],
            ]
            for col, value in enumerate(values):
                self._table.setItem(row, col, QTableWidgetItem(str(value)))
        self._repaint_rows()

    def _repaint_rows(self) -> None:
        colors = task_status_colors()
        for row, data in enumerate(self._rows):
            item = self._table.item(row, 2)
            brushes = colors.get(str(data["status"]).lower())
            if item is not None and brushes:
                item.setBackground(brushes["bg"])
                item.setForeground(brushes["fg"])

    def _on_new_task(self) -> None:
        dialog = SearchTaskDialog(parent=self, incident_id=self._incident_id)
        if dialog.exec():
            fields = dialog.result_fields()
            try:
                search_task_repository.publish_search_task(incident_id=self._incident_id, **fields)
            except Exception as exc:
                QMessageBox.critical(self, "Search Assignment Planner", f"Failed to publish task:\n{exc}")
                return
            self.reload()
