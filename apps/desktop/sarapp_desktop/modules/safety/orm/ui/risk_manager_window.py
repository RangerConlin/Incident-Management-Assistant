"""Qt window for the incident-wide safety hazard register."""

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
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from utils.state import AppState

from .. import pdf_export, service
from ..models import Hazard
from .incident_hazard_detail_window import IncidentHazardDetailWindow

_HEADERS = [
    "Hazard",
    "Category",
    "Initial SPE",
    "Residual SPE",
    "Op Periods",
    "Linked Items",
    "Hazard Zones",
    "Source",
    "Updated",
]
_SPE_BANDS = ["Very High", "High", "Substantial", "Possible", "Slight", "Not assessed"]


def _spe_cell(assessment) -> str:
    if not assessment:
        return "Not assessed"
    return f"{assessment.score} - {assessment.band}"


def _spe_band(assessment) -> str:
    if not assessment:
        return "Not assessed"
    return assessment.band or "Not assessed"


def _join_ids(values: list[int]) -> str:
    return ", ".join(str(value) for value in values) if values else "None"


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

    def row_values(self, hazard: Hazard) -> list[str]:
        return [
            hazard.title,
            hazard.category or "",
            _spe_cell(hazard.default_spe),
            _spe_cell(hazard.spe_residual),
            _join_ids(hazard.op_period_ids),
            str(_link_count(hazard)),
            str(len(hazard.hazard_zone_ids)),
            hazard.source or "",
            hazard.updated_at or hazard.created_at or "",
        ]


class RiskManagerWindow(QWidget):
    """Main QWidget for managing the canonical incident hazard register."""

    def __init__(self, incident_id: Optional[object] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Incident Hazard Register")
        self._incident_id = self._normalize_incident_id(
            incident_id if incident_id is not None else self._resolve_incident_id()
        )
        self._model = HazardTableModel()

        self._build_ui()
        self._load_hazards()

    # ------------------------------------------------------------------ UI build
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        title_stack = QVBoxLayout()
        title = QLabel("Incident Hazard Register")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        subtitle = QLabel(
            "Manage all hazards for this incident, including controls, PPE, safety language, SPE scores, and links."
        )
        subtitle.setStyleSheet("color: #5f6b7a;")
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)
        header_row.addLayout(title_stack, 1)

        self.add_button = QPushButton("Add Hazard")
        self.add_button.clicked.connect(self._add_hazard)
        header_row.addWidget(self.add_button)

        self.import_button = QPushButton("Import From Library")
        self.import_button.clicked.connect(self._add_hazard)
        header_row.addWidget(self.import_button)

        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self._edit_hazard)
        header_row.addWidget(self.edit_button)

        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self._remove_hazard)
        header_row.addWidget(self.remove_button)
        layout.addLayout(header_row)

        summary_grid = QGridLayout()
        summary_grid.setHorizontalSpacing(10)
        self.total_card = self._summary_card("Total Hazards", "0")
        self.initial_high_card = self._summary_card("High Initial SPE", "0")
        self.residual_high_card = self._summary_card("High Residual SPE", "0")
        self.unlinked_card = self._summary_card("Unlinked Hazards", "0")
        self.zoned_card = self._summary_card("Hazards With Zones", "0")
        for col, card in enumerate(
            [
                self.total_card,
                self.initial_high_card,
                self.residual_high_card,
                self.unlinked_card,
                self.zoned_card,
            ]
        ):
            summary_grid.addWidget(card, 0, col)
        layout.addLayout(summary_grid)

        filter_row = QHBoxLayout()
        self.search_filter = QLineEdit()
        self.search_filter.setPlaceholderText("Search hazards, controls, PPE, safety language, or notes")
        self.search_filter.textChanged.connect(self._refresh_table)
        filter_row.addWidget(self.search_filter, 2)

        filter_row.addWidget(QLabel("Op Period"))
        self.op_filter = QComboBox()
        self.op_filter.addItem("All", None)
        for i in range(1, 21):
            self.op_filter.addItem(str(i), i)
        self.op_filter.currentIndexChanged.connect(self._load_hazards)
        filter_row.addWidget(self.op_filter)

        self.spe_filter = QComboBox()
        self.spe_filter.addItem("All SPE Bands", None)
        for band in _SPE_BANDS:
            self.spe_filter.addItem(band, band)
        self.spe_filter.currentIndexChanged.connect(self._refresh_table)
        filter_row.addWidget(self.spe_filter)

        self.source_filter = QComboBox()
        self.source_filter.addItem("All Sources", None)
        self.source_filter.addItem("Library", "library")
        self.source_filter.addItem("Incident Only", "incident")
        self.source_filter.currentIndexChanged.connect(self._refresh_table)
        filter_row.addWidget(self.source_filter)

        self.link_filter = QComboBox()
        self.link_filter.addItem("All Links", None)
        self.link_filter.addItem("Linked", "linked")
        self.link_filter.addItem("Unlinked", "unlinked")
        self.link_filter.currentIndexChanged.connect(self._refresh_table)
        filter_row.addWidget(self.link_filter)

        self.count_label = QLabel("0 hazards")
        filter_row.addWidget(self.count_label)
        layout.addLayout(filter_row)

        splitter = QSplitter(Qt.Vertical)
        self.table = QTableView()
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setSortingEnabled(False)
        self.table.doubleClicked.connect(self._edit_hazard)
        splitter.addWidget(self.table)

        self.detail_panel = self._build_detail_panel()
        splitter.addWidget(self.detail_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        actions_layout = QHBoxLayout()
        self.export_button = QPushButton("Export Register PDF")
        self.export_button.clicked.connect(self._export_pdf)
        actions_layout.addWidget(self.export_button)
        actions_layout.addStretch(1)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        actions_layout.addWidget(self.close_button)
        layout.addLayout(actions_layout)

    def _summary_card(self, title: str, value: str) -> QGroupBox:
        card = QGroupBox(title)
        card.setStyleSheet(
            "QGroupBox { font-weight: 600; border: 1px solid #d7dde5; border-radius: 8px; "
            "margin-top: 8px; padding: 8px; }"
        )
        card.value_label = QLabel(value)  # type: ignore[attr-defined]
        card.value_label.setStyleSheet("font-size: 24px; font-weight: 700;")  # type: ignore[attr-defined]
        layout = QVBoxLayout(card)
        layout.addWidget(card.value_label)  # type: ignore[attr-defined]
        return card

    def _build_detail_panel(self) -> QWidget:
        panel = QWidget()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)

        heading_row = QHBoxLayout()
        self.detail_title = QLabel("Selected Hazard Detail")
        self.detail_title.setStyleSheet("font-size: 17px; font-weight: 700;")
        heading_row.addWidget(self.detail_title, 1)
        self.detail_edit_button = QPushButton("Edit Hazard")
        self.detail_edit_button.clicked.connect(self._edit_hazard)
        heading_row.addWidget(self.detail_edit_button)
        outer.addLayout(heading_row)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        self.identity_detail = self._readonly_text("Select a hazard to see its details.")
        self.initial_spe_detail = self._readonly_text()
        self.residual_spe_detail = self._readonly_text()
        self.controls_detail = self._readonly_text()
        self.ppe_detail = self._readonly_text()
        self.language_detail = self._readonly_text()
        self.links_detail = self._readonly_text()
        self.notes_detail = self._readonly_text()

        grid.addWidget(self._detail_box("Identity", self.identity_detail), 0, 0)
        grid.addWidget(self._detail_box("Initial SPE", self.initial_spe_detail), 0, 1)
        grid.addWidget(self._detail_box("Residual SPE", self.residual_spe_detail), 0, 2)
        grid.addWidget(self._detail_box("Mitigation Controls", self.controls_detail), 1, 0)
        grid.addWidget(self._detail_box("PPE", self.ppe_detail), 1, 1)
        grid.addWidget(self._detail_box("Standard Safety Language", self.language_detail), 1, 2)
        grid.addWidget(self._detail_box("Links And Hazard Zones", self.links_detail), 2, 0, 1, 2)
        grid.addWidget(self._detail_box("Notes", self.notes_detail), 2, 2)
        outer.addLayout(grid, 1)
        return panel

    def _readonly_text(self, text: str = "") -> QPlainTextEdit:
        edit = QPlainTextEdit(text)
        edit.setReadOnly(True)
        edit.setMinimumHeight(72)
        edit.setStyleSheet("QPlainTextEdit { background: #fbfcfe; border: 1px solid #d7dde5; }")
        return edit

    def _detail_box(self, title: str, widget: QWidget) -> QGroupBox:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 10, 8, 8)
        layout.addWidget(widget)
        return box

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

    def _filtered_hazards(self) -> list[Hazard]:
        hazards = self._model.hazards()
        needle = self.search_filter.text().strip().lower()
        selected_spe = self.spe_filter.currentData()
        selected_source = self.source_filter.currentData()
        selected_link_state = self.link_filter.currentData()

        if needle:
            hazards = [
                hazard
                for hazard in hazards
                if needle
                in "\n".join(
                    [
                        hazard.title or "",
                        hazard.description or "",
                        hazard.category or "",
                        hazard.control_measure or "",
                        hazard.mitigation_text or "",
                        hazard.ppe_text or "",
                        hazard.safety_message or "",
                        hazard.notes or "",
                    ]
                ).lower()
            ]
        if selected_spe:
            hazards = [
                hazard
                for hazard in hazards
                if _spe_band(hazard.default_spe) == selected_spe
                or _spe_band(hazard.spe_residual) == selected_spe
            ]
        if selected_source:
            hazards = [hazard for hazard in hazards if (hazard.source or "") == selected_source]
        if selected_link_state == "linked":
            hazards = [hazard for hazard in hazards if _link_count(hazard) > 0]
        elif selected_link_state == "unlinked":
            hazards = [hazard for hazard in hazards if _link_count(hazard) == 0]
        return hazards

    def _set_summary_value(self, card: QGroupBox, value: int) -> None:
        card.value_label.setText(str(value))  # type: ignore[attr-defined]

    def _load_hazards(self) -> None:
        if self._incident_id is None:
            QMessageBox.warning(
                self, "Incident Required", "Select an incident to use the Incident Hazard Register."
            )
            self.setDisabled(True)
            return
        hazards = service.list_hazards(self._incident_id, op_period=self._current_op_period())
        self._model.set_hazards(hazards)
        self._update_summary_cards(hazards)
        self._refresh_table()

    def _refresh_table(self) -> None:
        hazards = self._filtered_hazards()
        table_model = QStandardItemModel(len(hazards), len(_HEADERS))
        table_model.setHorizontalHeaderLabels(_HEADERS)
        for row, hazard in enumerate(hazards):
            for column, value in enumerate(self._model.row_values(hazard)):
                item = QStandardItem(value)
                item.setEditable(False)
                table_model.setItem(row, column, item)
        self.table.setModel(table_model)
        if self.table.selectionModel():
            self.table.selectionModel().selectionChanged.connect(self._update_buttons)
            self.table.selectionModel().selectionChanged.connect(self._update_detail)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, len(_HEADERS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.count_label.setText(f"{len(hazards)} hazard{'s' if len(hazards) != 1 else ''}")
        self._update_buttons()
        self._update_detail()

    def _update_summary_cards(self, hazards: list[Hazard]) -> None:
        high_bands = {"High", "Very High"}
        self._set_summary_value(self.total_card, len(hazards))
        self._set_summary_value(
            self.initial_high_card,
            sum(1 for hazard in hazards if _spe_band(hazard.default_spe) in high_bands),
        )
        self._set_summary_value(
            self.residual_high_card,
            sum(1 for hazard in hazards if _spe_band(hazard.spe_residual) in high_bands),
        )
        self._set_summary_value(self.unlinked_card, sum(1 for hazard in hazards if _link_count(hazard) == 0))
        self._set_summary_value(self.zoned_card, sum(1 for hazard in hazards if hazard.hazard_zone_ids))

    def _update_buttons(self) -> None:
        has_selection = bool(self.table.selectionModel() and self.table.selectionModel().hasSelection())
        self.edit_button.setEnabled(has_selection)
        self.remove_button.setEnabled(has_selection)
        self.detail_edit_button.setEnabled(has_selection)

    def _update_detail(self) -> None:
        hazard = self._selected_hazard()
        if hazard is None:
            self.detail_title.setText("Selected Hazard Detail")
            self.identity_detail.setPlainText("Select a hazard to see its details.")
            for edit in (
                self.initial_spe_detail,
                self.residual_spe_detail,
                self.controls_detail,
                self.ppe_detail,
                self.language_detail,
                self.links_detail,
                self.notes_detail,
            ):
                edit.clear()
            return

        self.detail_title.setText(hazard.title or "Selected Hazard Detail")
        self.identity_detail.setPlainText(
            "\n".join(
                [
                    f"Category: {hazard.category or 'None'}",
                    f"Source: {hazard.source or 'None'}",
                    f"Library hazard type: {hazard.hazard_type_id or 'Incident-only'}",
                    f"Location: {hazard.location_text or 'None'}",
                    "",
                    hazard.description or "No description.",
                ]
            )
        )
        self.initial_spe_detail.setPlainText(self._spe_detail_text(hazard.default_spe))
        self.residual_spe_detail.setPlainText(self._spe_detail_text(hazard.spe_residual))
        self.controls_detail.setPlainText(hazard.control_measure or "No mitigation controls entered.")
        self.ppe_detail.setPlainText(hazard.ppe_text or "No PPE entered.")
        self.language_detail.setPlainText(
            hazard.safety_message or hazard.mitigation_text or "No standard safety language entered."
        )
        links = hazard.links
        self.links_detail.setPlainText(
            "\n".join(
                [
                    f"Operational periods: {_join_ids(hazard.op_period_ids)}",
                    f"Work assignments: {_join_ids(links.work_assignment_ids)}",
                    f"Teams: {_join_ids(links.team_ids)}",
                    f"Tasks: {_join_ids(links.task_ids)}",
                    f"Hazard zones: {_join_ids(hazard.hazard_zone_ids)}",
                ]
            )
        )
        self.notes_detail.setPlainText(hazard.notes or "No notes.")

    def _spe_detail_text(self, assessment) -> str:
        if not assessment:
            return "Not assessed."
        return "\n".join(
            [
                f"Severity: {assessment.severity}",
                f"Probability: {assessment.probability}",
                f"Exposure: {assessment.exposure}",
                f"Score: {assessment.score}",
                f"Band: {assessment.band}",
                f"Action: {assessment.action}",
            ]
        )

    # ------------------------------------------------------------------ slots
    def _selected_hazard(self) -> Optional[Hazard]:
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        hazards = self._filtered_hazards()
        if 0 <= index.row() < len(hazards):
            return hazards[index.row()]
        return None

    def _add_hazard(self) -> None:
        if self._incident_id is None:
            return
        default_op = self._current_op_period() or (AppState.get_active_op_period() or 1)
        dialog = IncidentHazardDetailWindow(self._incident_id, self, default_op_period=default_op)
        if dialog.exec() == QDialog.Accepted:
            payload = dialog.result_payload()
            if payload:
                service.create_hazard(self._incident_id, payload)
                self._load_hazards()

    def _edit_hazard(self) -> None:
        hazard = self._selected_hazard()
        if hazard is None or self._incident_id is None:
            return
        dialog = IncidentHazardDetailWindow(self._incident_id, self, hazard=asdict(hazard))
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
        filename = f"IncidentHazardRegister_{self._incident_id}.pdf"
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
