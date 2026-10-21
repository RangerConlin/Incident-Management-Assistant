"""Search Segment Manager panel (SAR Toolkit).

Maintains the canonical SAR search segment list per
docs/archive/design-documents/toolkit_sar_playbook.md. All reads/writes go
through utils/api_client.py via modules.sartoolkit.data.segments_repository
— no direct DB access from this panel (agents.md hard rule).
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

from modules.sartoolkit.data import segments_repository
from modules.sartoolkit.models.segment import SearchSegment
from modules.sartoolkit.panels.auto_grid_dialog import AutoGridDialog
from modules.sartoolkit.panels.segment_dialog import SegmentDialog
from utils.table_view_styles import apply_statusboard_table_behavior
from utils.styles import (
    get_palette,
    segment_planning_status_colors,
    segment_review_status_colors,
    segment_search_status_colors,
    subscribe_theme,
)

_COLUMNS = [
    "Name",
    "Planning Status",
    "Search Status",
    "Review Status",
    "Size (acres)",
    "Map Reference",
    "GIS",
    "Parent",
    "Updated",
]


class SegmentManagerPanel(QWidget):
    panel_title = "Search Segment Manager"

    def __init__(self, incident_id: object | None = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._incident_id = str(incident_id) if incident_id else None
        self._segments: list[SearchSegment] = []
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

        self._btn_new = QPushButton("+ New Segment")
        self._btn_new.clicked.connect(self._on_new_segment)
        header.addWidget(self._btn_new)

        self._btn_grid = QPushButton("Auto-Create Grid...")
        self._btn_grid.clicked.connect(self._on_auto_grid)
        header.addWidget(self._btn_grid)

        self._btn_edit = QPushButton("Edit")
        self._btn_edit.clicked.connect(self._on_edit_segment)
        header.addWidget(self._btn_edit)

        self._btn_delete = QPushButton("Delete")
        self._btn_delete.clicked.connect(self._on_delete_segment)
        header.addWidget(self._btn_delete)

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
        self._table.doubleClicked.connect(lambda *_: self._on_edit_segment())
        apply_statusboard_table_behavior(self._table, stretch_last_section=True)
        root.addWidget(self._table, 1)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"color:{get_palette().get('fg_muted').name()};")
        root.addWidget(self._status_label)

    def reload(self) -> None:
        try:
            self._segments = segments_repository.list_segments(self._incident_id)
            self._status_label.setText(f"{len(self._segments)} segment(s)")
        except Exception as exc:
            QMessageBox.critical(self, "Search Segment Manager", f"Failed to load segments:\n{exc}")
            self._segments = []
        self._render_table()

    def _render_table(self) -> None:
        self._table.setRowCount(len(self._segments))
        for row, seg in enumerate(self._segments):
            values = [
                seg.name,
                seg.planning_status,
                seg.search_status,
                seg.review_status,
                f"{seg.size_estimate:g}" if seg.size_estimate else "",
                seg.map_reference,
                "Yes" if seg.gis_reference else "No",
                seg.parent_segment_id or "",
                seg.updated_at,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, seg.segment_id)
                self._table.setItem(row, col, item)
        self._repaint_rows()

    def _repaint_rows(self) -> None:
        planning_colors = segment_planning_status_colors()
        search_colors = segment_search_status_colors()
        review_colors = segment_review_status_colors()
        for row, seg in enumerate(self._segments):
            self._apply_badge(row, 1, planning_colors.get(seg.planning_status))
            self._apply_badge(row, 2, search_colors.get(seg.search_status))
            self._apply_badge(row, 3, review_colors.get(seg.review_status))

    def _apply_badge(self, row: int, col: int, brushes: Optional[dict]) -> None:
        item = self._table.item(row, col)
        if item is None or not brushes:
            return
        item.setBackground(brushes["bg"])
        item.setForeground(brushes["fg"])

    def _selected_segment(self) -> Optional[SearchSegment]:
        rows = self._table.selectionModel().selectedRows() if self._table.selectionModel() else []
        if not rows:
            return None
        idx = rows[0].row()
        if idx < 0 or idx >= len(self._segments):
            return None
        return self._segments[idx]

    def _on_new_segment(self) -> None:
        dialog = SegmentDialog(parent=self)
        if dialog.exec():
            segment = dialog.result_segment()
            try:
                segments_repository.create_segment(segment, self._incident_id)
            except Exception as exc:
                QMessageBox.critical(self, "Search Segment Manager", f"Failed to create segment:\n{exc}")
                return
            self.reload()

    def _on_edit_segment(self) -> None:
        segment = self._selected_segment()
        if segment is None:
            QMessageBox.information(self, "Search Segment Manager", "Select a segment to edit.")
            return
        dialog = SegmentDialog(segment=segment, parent=self)
        if dialog.exec():
            updated = dialog.result_segment()
            try:
                segments_repository.update_segment(updated, self._incident_id)
            except Exception as exc:
                QMessageBox.critical(self, "Search Segment Manager", f"Failed to update segment:\n{exc}")
                return
            self.reload()

    def _on_delete_segment(self) -> None:
        segment = self._selected_segment()
        if segment is None:
            QMessageBox.information(self, "Search Segment Manager", "Select a segment to delete.")
            return
        reply = QMessageBox.question(self, "Delete Segment", f"Delete segment '{segment.name}'?")
        if reply != QMessageBox.Yes:
            return
        try:
            segments_repository.delete_segment(segment.segment_id, self._incident_id)
        except Exception as exc:
            QMessageBox.critical(self, "Search Segment Manager", f"Failed to delete segment:\n{exc}")
            return
        self.reload()

    def _on_auto_grid(self) -> None:
        dialog = AutoGridDialog(parent=self)
        if dialog.exec():
            params = dialog.result_params()
            try:
                created = segments_repository.auto_create_grid(params, self._incident_id)
            except Exception as exc:
                QMessageBox.critical(self, "Auto-Create Grid", f"Failed to create grid:\n{exc}")
                return
            QMessageBox.information(self, "Auto-Create Grid", f"Created {len(created)} segment(s).")
            self.reload()
