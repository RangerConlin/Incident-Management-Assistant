"""Qt window for the Safety Risk Manager (canonical incident hazard register)."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from utils.state import AppState

from .. import pdf_export, service
from ..models import Hazard
from .hazard_editor import HazardEditorDialog

_HEADERS = ["Title", "Category", "Op Period(s)", "Initial SPE", "Residual SPE", "Links"]


def _spe_cell(assessment) -> str:
    if not assessment:
        return "Not assessed"
    return f"{assessment.score} — {assessment.band}"


def _link_count(hazard: Hazard) -> int:
    links = hazard.links
    return len(links.work_assignment_ids) + len(links.team_ids) + len(links.task_ids)


class HazardTableModel:
    headers = _HEADERS

    def __init__(self) -> None:
        self._hazards: list[Hazard] = []

    def set_hazards(self, hazards: list[Hazard]) -> None:
        self._hazards = list(hazards)

    def hazards(self) -> list[Hazard]:
        return list(self._hazards)

    def hazard_at(self, row: int) -> Optional[Hazard]:
        if 0 <= row < len(self._hazards):
            return self._hazards[row]
        return None

    def row_values(self, hazard: Hazard) -> list[str]:
        return [
            hazard.title,
            hazard.category or "",
            ", ".join(str(op) for op in hazard.op_period_ids),
            _spe_cell(hazard.spe_initial),
            _spe_cell(hazard.spe_residual),
            str(_link_count(hazard)),
        ]


class RiskManagerWindow(QWidget):
    """Main QWidget for managing the canonical incident hazard register."""

    def __init__(self, incident_id: Optional[object] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Safety Risk Manager")
        self._incident_id = self._normalize_incident_id(
            incident_id if incident_id is not None else self._resolve_incident_id()
        )
        self._model = HazardTableModel()

        self._build_ui()
        self._load_hazards()

    # ------------------------------------------------------------------ UI build
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("Op Period"))
        self.op_filter = QComboBox()
        self.op_filter.addItem("All", None)
        for i in range(1, 21):
            self.op_filter.addItem(str(i), i)
        self.op_filter.currentIndexChanged.connect(self._load_hazards)
        toolbar.addWidget(self.op_filter)

        toolbar.addSpacing(12)

        self.add_button = QPushButton("Add Hazard")
        self.add_button.clicked.connect(self._add_hazard)
        toolbar.addWidget(self.add_button)

        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self._edit_hazard)
        toolbar.addWidget(self.edit_button)

        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self._remove_hazard)
        toolbar.addWidget(self.remove_button)

        toolbar.addStretch(1)
        self.count_label = QLabel("0 hazards")
        toolbar.addWidget(self.count_label)

        layout.addLayout(toolbar)

        self.table = QTableView()
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setSortingEnabled(False)
        self.table.doubleClicked.connect(self._edit_hazard)
        layout.addWidget(self.table, 1)

        actions_layout = QHBoxLayout()
        self.export_button = QPushButton("Export Register PDF")
        self.export_button.clicked.connect(self._export_pdf)
        actions_layout.addWidget(self.export_button)
        actions_layout.addStretch(1)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        actions_layout.addWidget(self.close_button)
        layout.addLayout(actions_layout)

    # ------------------------------------------------------------------ helpers
    def _normalize_incident_id(self, value: Optional[object]) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, (int, str)):
            text = str(value).strip()
            return text or None
        for attr in ("number", "id", "incident_id"):
            candidate = getattr(value, attr, None)
            normalized = self._normalize_incident_id(candidate)
            if normalized is not None:
                return normalized
        return None

    def _resolve_incident_id(self) -> Optional[object]:
        incident = AppState.get_active_incident()
        normalized = self._normalize_incident_id(incident)
        if normalized is not None:
            return normalized
        try:
            from utils import incident_context

            return self._normalize_incident_id(incident_context.get_active_incident_id())
        except Exception:
            return None

    def _current_op_period(self) -> Optional[int]:
        return self.op_filter.currentData()

    def _load_hazards(self) -> None:
        if self._incident_id is None:
            QMessageBox.warning(
                self, "Incident Required", "Select an incident to use the Safety Risk Manager."
            )
            self.setDisabled(True)
            return
        hazards = service.list_hazards(self._incident_id, op_period=self._current_op_period())
        self._model.set_hazards(hazards)
        self._refresh_table()

    def _refresh_table(self) -> None:
        model = self._model
        hazards = model.hazards()
        table_model = QStandardItemModel(len(hazards), len(_HEADERS))
        table_model.setHorizontalHeaderLabels(_HEADERS)
        for row, hazard in enumerate(hazards):
            for column, value in enumerate(model.row_values(hazard)):
                table_model.setItem(row, column, QStandardItem(value))
        self.table.setModel(table_model)
        self.table.resizeColumnsToContents()
        if self.table.selectionModel():
            self.table.selectionModel().selectionChanged.connect(self._update_buttons)
        self.count_label.setText(f"{len(hazards)} hazard{'s' if len(hazards) != 1 else ''}")
        self._update_buttons()

    def _update_buttons(self) -> None:
        has_selection = bool(self.table.selectionModel() and self.table.selectionModel().hasSelection())
        self.edit_button.setEnabled(has_selection)
        self.remove_button.setEnabled(has_selection)

    # ------------------------------------------------------------------ slots
    def _selected_hazard(self) -> Optional[Hazard]:
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        return self._model.hazard_at(index.row())

    def _add_hazard(self) -> None:
        if self._incident_id is None:
            return
        default_op = self._current_op_period() or (AppState.get_active_op_period() or 1)
        dialog = HazardEditorDialog(self._incident_id, self, default_op_period=default_op)
        if dialog.exec() == QDialog.Accepted:
            payload = dialog.result_payload()
            if payload:
                service.create_hazard(self._incident_id, payload)
                self._load_hazards()

    def _edit_hazard(self) -> None:
        hazard = self._selected_hazard()
        if hazard is None or self._incident_id is None:
            return
        dialog = HazardEditorDialog(self._incident_id, self, hazard=asdict(hazard))
        if dialog.exec() == QDialog.Accepted:
            payload = dialog.result_payload()
            if payload:
                service.update_hazard(self._incident_id, hazard.id, payload)
                self._load_hazards()

    def _remove_hazard(self) -> None:
        hazard = self._selected_hazard()
        if hazard is None or self._incident_id is None:
            return
        if (
            QMessageBox.question(self, "Remove Hazard", f"Remove hazard '{hazard.title}'?")
            == QMessageBox.Yes
        ):
            service.delete_hazard(self._incident_id, hazard.id)
            self._load_hazards()

    def _export_pdf(self) -> None:
        if self._incident_id is None:
            return
        hazards = self._model.hazards()
        filename = f"SafetyRiskRegister_Incident{self._incident_id}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF", str(Path.home() / filename), "PDF Files (*.pdf)"
        )
        if path:
            try:
                data = pdf_export.build_pdf(hazards=hazards)
                Path(path).write_bytes(data)
                QMessageBox.information(self, "Exported", f"Saved to {path}")
            except Exception as exc:
                QMessageBox.critical(self, "Export Failed", str(exc))
