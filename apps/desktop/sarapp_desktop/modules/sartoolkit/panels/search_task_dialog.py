"""+ New Task dialog (SAR Toolkit — Search Assignment Planner).

"Publish to Task Board" calls the existing Operations tasking creation API
to create the real task record, then links a search_task_details record to
it — see modules/sartoolkit/data/search_task_repository.py.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.sartoolkit.data import segments_repository
from modules.sartoolkit.models.search_task import SEARCH_METHODS


class SearchTaskDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None, incident_id: Optional[str] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Search Task")
        self.setMinimumWidth(460)
        self._incident_id = incident_id

        form = QFormLayout()

        self.cmb_segment = QComboBox()
        self._segments_by_index: list[str] = []
        try:
            for seg in segments_repository.list_segments(incident_id):
                self.cmb_segment.addItem(f"{seg.name} ({seg.segment_id[:8]})")
                self._segments_by_index.append(seg.segment_id)
        except Exception:
            pass
        form.addRow("Segment", self.cmb_segment)

        self.ed_title = QLineEdit()
        self.ed_title.setPlaceholderText("Task title (e.g. 'Segment 3 hasty search')")
        form.addRow("Title", self.ed_title)

        self.ed_resource = QLineEdit()
        self.ed_resource.setPlaceholderText("Team / resource")
        form.addRow("Team / Resource", self.ed_resource)

        self.ed_team_leader = QLineEdit()
        form.addRow("Team Leader", self.ed_team_leader)

        self.ed_radio = QLineEdit()
        form.addRow("Radio Channel", self.ed_radio)

        self.cmb_method = QComboBox()
        self.cmb_method.addItems(SEARCH_METHODS)
        form.addRow("Search Method", self.cmb_method)

        self.ed_spacing = QLineEdit()
        self.ed_spacing.setPlaceholderText("e.g. 20m")
        form.addRow("Track Spacing", self.ed_spacing)

        self.dt_departure = QDateTimeEdit()
        self.dt_departure.setCalendarPopup(True)
        self.dt_departure.setDisplayFormat("yyyy-MM-dd HH:mm")
        form.addRow("Departure Time", self.dt_departure)

        self.dt_due_back = QDateTimeEdit()
        self.dt_due_back.setCalendarPopup(True)
        self.dt_due_back.setDisplayFormat("yyyy-MM-dd HH:mm")
        form.addRow("Due-Back Time", self.dt_due_back)

        self.ed_completion = QPlainTextEdit()
        self.ed_completion.setFixedHeight(50)
        form.addRow("Completion Criteria", self.ed_completion)

        self.ed_safety = QPlainTextEdit()
        self.ed_safety.setFixedHeight(50)
        form.addRow("Safety Notes", self.ed_safety)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Publish to Task Board")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(buttons)

    def _on_accept(self) -> None:
        if not self.ed_title.text().strip():
            self.ed_title.setFocus()
            return
        self.accept()

    def selected_segment_id(self) -> Optional[str]:
        idx = self.cmb_segment.currentIndex()
        if 0 <= idx < len(self._segments_by_index):
            return self._segments_by_index[idx]
        return None

    def result_fields(self) -> dict:
        return {
            "title": self.ed_title.text().strip(),
            "segment_id": self.selected_segment_id(),
            "team_or_resource": self.ed_resource.text().strip(),
            "team_leader": self.ed_team_leader.text().strip(),
            "radio_channel": self.ed_radio.text().strip(),
            "search_method": self.cmb_method.currentText(),
            "track_spacing": self.ed_spacing.text().strip(),
            "departure_time": self.dt_departure.dateTime().toString("yyyy-MM-dd HH:mm"),
            "due_back_time": self.dt_due_back.dateTime().toString("yyyy-MM-dd HH:mm"),
            "completion_criteria": self.ed_completion.toPlainText().strip(),
            "safety_notes": self.ed_safety.toPlainText().strip(),
        }
