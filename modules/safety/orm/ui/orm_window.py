"""Qt window for managing CAP ORM per operational period."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QDateTime, QModelIndex, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateTimeEdit,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from utils.state import AppState

from .. import pdf_export, service
from ..models import ORMForm, ORMHazard
from ..service import RISK_LEVELS, RISK_ORDER
from .hazard_editor import HazardEditorDialog


class HazardTableModel:
    headers = [
        "#",
        "Sub-Activity",
        "Hazard / Outcome",
        "Initial",
        "Control(s)",
        "Residual",
        "How",
        "Who",
    ]

    def __init__(self) -> None:
        self._hazards: list[ORMHazard] = []

    def set_hazards(self, hazards: list[ORMHazard]) -> None:
        self._hazards = list(hazards)

    def row_count(self) -> int:
        return len(self._hazards)

    def column_count(self) -> int:
        return len(self.headers)

    def data(self, row: int, column: int, role: int = Qt.DisplayRole) -> Optional[str]:
        if row >= len(self._hazards):
            return None
        hazard = self._hazards[row]
        if role == Qt.DisplayRole:
            if column == 0:
                return str(row + 1)
            mapping = {
                1: hazard.sub_activity,
                2: hazard.hazard_outcome,
                3: hazard.initial_risk,
                4: hazard.control_text,
                5: hazard.residual_risk,
                6: hazard.implement_how or "",
                7: hazard.implement_who or "",
            }
            return mapping.get(column, "")
        if role == Qt.TextAlignmentRole and column == 0:
            return int(Qt.AlignCenter)
        if role == Qt.UserRole and column in {3, 5}:
            value = hazard.initial_risk if column == 3 else hazard.residual_risk
            return RISK_ORDER.get(value, 0)
        return None

    def hazard_at(self, row: int) -> Optional[ORMHazard]:
        if 0 <= row < len(self._hazards):
            return self._hazards[row]
        return None

    def hazards(self) -> list[ORMHazard]:
        return list(self._hazards)


class ORMWindow(QWidget):
    """Main QWidget for editing CAP ORM data."""

    def __init__(self, incident_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CAP ORM (Per OP)")
        self._incident_id = (
            incident_id if incident_id is not None else self._resolve_incident_id()
        )
        self._current_op = AppState.get_active_op_period() or 1
        self._form: Optional[ORMForm] = None
        self._model = HazardTableModel()

        self._build_ui()
        self._load_form()

    # ------------------------------------------------------------------ UI build
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_widget = QWidget(self)
        header_layout = QGridLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setHorizontalSpacing(8)
        header_layout.setVerticalSpacing(6)

        self.op_combo = QComboBox()
        self.op_combo.addItems([str(i) for i in range(1, 21)])
        self.op_combo.setCurrentText(str(self._current_op))
        self.op_combo.currentTextChanged.connect(self._on_op_changed)
        header_layout.addWidget(QLabel("Operational Period"), 0, 0)
        header_layout.addWidget(self.op_combo, 0, 1)

        self.prepared_label = QLabel(self._prepared_by_text())
        self.prepared_label.setToolTip("Prepared By (read-only)")
        header_layout.addWidget(QLabel("Prepared By"), 0, 2)
        header_layout.addWidget(self.prepared_label, 0, 3)

        self.date_edit = QDateTimeEdit(QDateTime.currentDateTime())
        self.date_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.date_edit.dateTimeChanged.connect(self._save_header)
        header_layout.addWidget(QLabel("Date"), 0, 4)
        header_layout.addWidget(self.date_edit, 0, 5)

        self.activity_edit = QLineEdit()
        self.activity_edit.setPlaceholderText("e.g., Ground Team Operations — OP 4")
        self.activity_edit.editingFinished.connect(self._save_header)
        header_layout.addWidget(QLabel("Activity"), 0, 6)
        header_layout.addWidget(self.activity_edit, 0, 7)

        self.risk_chip = QLabel("L")
        self.risk_chip.setAlignment(Qt.AlignCenter)
        self.risk_chip.setStyleSheet(self._chip_style("L"))
        self.risk_chip.setFixedHeight(28)
        header_layout.addWidget(self.risk_chip, 0, 8)

        self.status_chip = QLabel("Draft")
        self.status_chip.setAlignment(Qt.AlignCenter)
        self.status_chip.setStyleSheet(self._status_style("draft"))
        self.status_chip.setFixedHeight(28)
        header_layout.addWidget(self.status_chip, 0, 9)

        layout.addWidget(header_widget)

        self.block_banner = QFrame()
        self.block_banner.setFrameShape(QFrame.StyledPanel)
        self.block_banner.setStyleSheet(
            "background-color: #b71c1c; color: white; padding: 8px; font-weight: 600;"
        )
        banner_layout = QHBoxLayout(self.block_banner)
        banner_layout.setContentsMargins(8, 4, 8, 4)
        self.block_label = QLabel(
            "Approval Blocked: Reduce residual risk to Medium or Low to proceed."
        )
        banner_layout.addWidget(self.block_label)
        self.block_banner.hide()
        layout.addWidget(self.block_banner)

        # Hazard table region
        table_container = QWidget(self)
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(6)

        toolbar = QHBoxLayout()
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
        table_layout.addLayout(toolbar)

        self.table = QTableView()
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setSortingEnabled(False)
        self.table.doubleClicked.connect(self._edit_hazard)
        table_layout.addWidget(self.table)

        self.footer_label = QLabel("Highest Residual Risk: L")
        self.footer_label.setAlignment(Qt.AlignRight)
        table_layout.addWidget(self.footer_label)

        layout.addWidget(table_container, 1)

        # Action bar
        actions_layout = QHBoxLayout()
        self.export_button = QPushButton("Export PDF")
        self.export_button.clicked.connect(self._export_pdf)
        actions_layout.addWidget(self.export_button)

        actions_layout.addStretch(1)

        self.approve_button = QPushButton("Approve")
        self.approve_button.clicked.connect(self._approve)
        actions_layout.addWidget(self.approve_button)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        actions_layout.addWidget(self.close_button)

        layout.addLayout(actions_layout)

    # ------------------------------------------------------------------ helpers
    def _resolve_incident_id(self) -> Optional[int]:
        incident = AppState.get_active_incident()
        if incident is None:
            return None
        try:
            return int(str(incident))
        except ValueError:
            return None

    def _prepared_by_text(self) -> str:
        user = AppState.get_active_user_id()
        return str(user) if user is not None else "(not set)"

    def _chip_style(self, risk: str) -> str:
        palette = {
            "L": "#2e7d32",
            "M": "#f9a825",
            "H": "#ef6c00",
            "EH": "#c62828",
        }
        color = palette.get(risk, "#616161")
        return (
            "border-radius: 14px; padding: 4px 12px; font-weight: 600; "
            f"background-color: {color}; color: white;"
        )

    def _status_style(self, status: str) -> str:
        palette = {
            "draft": "#546e7a",
            "pending_mitigation": "#ef6c00",
            "approved": "#2e7d32",
        }
        color = palette.get(status, "#455a64")
        text = status.replace("_", " ").title()
        self.status_chip.setText(text)
        return (
            "border-radius: 14px; padding: 4px 12px; font-weight: 600; "
            f"background-color: {color}; color: white;"
        )

    def _load_form(self) -> None:
        if self._incident_id is None:
            QMessageBox.warning(
                self, "Incident Required", "Select an incident to use the CAP ORM module."
            )
            self.setDisabled(True)
            return
        op = int(self.op_combo.currentText())
        self._current_op = op
        form = service.ensure_form(self._incident_id, op)
        self._form = form
        hazards = service.list_hazards(self._incident_id, op)
        self._model.set_hazards(hazards)
        self._refresh_table()
        self._refresh_header()

    def _refresh_header(self) -> None:
        if not self._form:
            return
        if self._form.activity:
            self.activity_edit.setText(self._form.activity)
        else:
            self.activity_edit.clear()
        if self._form.date_iso:
            try:
                self.date_edit.setDateTime(QDateTime.fromString(self._form.date_iso, Qt.ISODate))
            except Exception:
                pass
        self.prepared_label.setText(self._prepared_by_text())
        self._update_status_widgets()

    def _refresh_table(self) -> None:
        model = self._model
        rows = model.row_count()
        qt_model = self.table.model()
        from PySide6.QtGui import QStandardItemModel, QStandardItem

        table_model = QStandardItemModel(rows, model.column_count())
        table_model.setHorizontalHeaderLabels(model.headers)
        for row in range(rows):
            for column in range(model.column_count()):
                value = model.data(row, column, Qt.DisplayRole)
                item = QStandardItem(value or "")
                if column in {3, 5}:
                    sort_value = model.data(row, column, Qt.UserRole)
                    item.setData(sort_value, Qt.UserRole)
                if column == 0:
                    item.setTextAlignment(Qt.AlignCenter)
                table_model.setItem(row, column, item)
        self.table.setModel(table_model)
        self.table.resizeColumnsToContents()
        self.count_label.setText(
            f"{rows} hazard{'s' if rows != 1 else ''} — "
            + ", ".join(
                f"{risk}: {count}" for risk, count in service.hazard_counts(model.hazards()).items()
            )
        )
        if rows == 0:
            self.footer_label.setText("No hazards yet. Click 'Add Hazard' to begin.")
        else:
            self.footer_label.setText(
                f"Highest Residual Risk: {self._form.highest_residual_risk if self._form else 'L'}"
            )
        self._update_status_widgets()
        self._update_buttons()

    def _update_status_widgets(self) -> None:
        if not self._form:
            return
        risk = self._form.highest_residual_risk
        self.risk_chip.setText(risk)
        self.risk_chip.setStyleSheet(self._chip_style(risk))
        self.status_chip.setStyleSheet(self._status_style(self._form.status))
        self.footer_label.setText(f"Highest Residual Risk: {risk}")
        self.block_banner.setVisible(self._form.approval_blocked)
        self.approve_button.setEnabled(not self._form.approval_blocked)
        if self._form.approval_blocked:
            self.approve_button.setToolTip(
                "Blocked by policy: highest residual risk is H/EH."
            )
        else:
            self.approve_button.setToolTip("")

    def _update_buttons(self) -> None:
        has_selection = bool(self.table.selectionModel() and self.table.selectionModel().hasSelection())
        self.edit_button.setEnabled(has_selection)
        self.remove_button.setEnabled(has_selection)

    # ------------------------------------------------------------------ slots
    def _on_op_changed(self, text: str) -> None:
        try:
            op = int(text)
        except ValueError:
            return
        self._current_op = op
        self._load_form()

    def _save_header(self) -> None:
        if not self._form or self._incident_id is None:
            return
        payload = {
            "activity": self.activity_edit.text().strip() or None,
            "prepared_by_id": AppState.get_active_user_id(),
            "date_iso": self.date_edit.dateTime().toString(Qt.ISODate),
        }
        self._form = service.update_form_header(self._incident_id, self._current_op, payload)
        self._update_status_widgets()

    def _selected_hazard(self) -> Optional[ORMHazard]:
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        return self._model.hazard_at(index.row())

    def _add_hazard(self) -> None:
        dialog = HazardEditorDialog(self)
        if dialog.exec() == QDialog.Accepted:
            payload = dialog.result_payload()
            if payload and self._incident_id is not None:
                service.add_hazard(self._incident_id, self._current_op, payload)
                self._form = service.ensure_form(self._incident_id, self._current_op)
                self._model.set_hazards(
                    service.list_hazards(self._incident_id, self._current_op)
                )
                self._refresh_table()

    def _edit_hazard(self) -> None:
        hazard = self._selected_hazard()
        if hazard is None:
            return
        dialog = HazardEditorDialog(self, hazard=asdict(hazard))
        if dialog.exec() == QDialog.Accepted:
            payload = dialog.result_payload()
            if payload and self._incident_id is not None:
                service.edit_hazard(
                    self._incident_id, self._current_op, hazard.id, payload
                )
                self._form = service.ensure_form(self._incident_id, self._current_op)
                self._model.set_hazards(
                    service.list_hazards(self._incident_id, self._current_op)
                )
                self._refresh_table()

    def _remove_hazard(self) -> None:
        hazard = self._selected_hazard()
        if hazard is None or self._incident_id is None:
            return
        if (
            QMessageBox.question(
                self,
                "Remove Hazard",
                f"Remove hazard '{hazard.sub_activity}'?",
            )
            == QMessageBox.Yes
        ):
            service.remove_hazard(self._incident_id, self._current_op, hazard.id)
            self._form = service.ensure_form(self._incident_id, self._current_op)
            self._model.set_hazards(service.list_hazards(self._incident_id, self._current_op))
            self._refresh_table()

    def _approve(self) -> None:
        if self._incident_id is None:
            return
        try:
            self._form = service.attempt_approval(self._incident_id, self._current_op)
            QMessageBox.information(self, "Approved", "ORM form approved.")
        except service.ApprovalBlockedError as exc:
            QMessageBox.warning(
                self,
                "Approval Blocked",
                "Approval is blocked until highest residual risk is Medium or Low.",
            )
        finally:
            self._model.set_hazards(service.list_hazards(self._incident_id, self._current_op))
            self._refresh_table()

    def _export_pdf(self) -> None:
        if self._incident_id is None:
            return
        form = service.ensure_form(self._incident_id, self._current_op)
        hazards = service.list_hazards(self._incident_id, self._current_op)
        pdf_bytes = pdf_export.build_pdf(form=form, hazards=hazards)
        filename = f"ORM_OP{self._current_op}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save PDF",
            str(Path.home() / filename),
            "PDF Files (*.pdf)",
        )
        if path:
            try:
                with open(path, "wb") as fh:
                    fh.write(pdf_bytes)
                QMessageBox.information(self, "Exported", f"Saved to {path}")
            except OSError as exc:
                QMessageBox.critical(self, "Export Failed", str(exc))
