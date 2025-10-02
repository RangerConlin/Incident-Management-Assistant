"""Dialog for adding/editing CAP ORM hazards."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from .. import service
from .widgets.risk_matrix import RiskMatrixDialog


class HazardEditorDialog(QDialog):
    """Modal dialog used to add or edit a single hazard row."""

    def __init__(self, parent=None, hazard: Optional[dict] = None):
        super().__init__(parent)
        self.setWindowTitle("Add Hazard" if hazard is None else "Edit Hazard")
        self.setModal(True)
        self._result: Optional[dict] = None

        layout = QVBoxLayout(self)
        self._error_label = QLabel()
        self._error_label.setStyleSheet("color: #c62828; font-weight: 600;")
        self._error_label.hide()
        layout.addWidget(self._error_label)

        form = QFormLayout()
        layout.addLayout(form)

        self.sub_activity = QLineEdit()
        self.sub_activity.setPlaceholderText("e.g., Night travel in steep terrain")
        form.addRow("Sub-Activity", self.sub_activity)

        self.hazard_outcome = QPlainTextEdit()
        self.hazard_outcome.setPlaceholderText("e.g., Slips/falls leading to injury")
        self.hazard_outcome.setMinimumHeight(64)
        form.addRow("Hazard / Outcome", self.hazard_outcome)

        self.initial_risk = QComboBox()
        self.initial_risk.addItems(service.RISK_LEVELS)
        self.initial_risk_matrix = QPushButton("Risk Matrix…")
        self.initial_risk_matrix.clicked.connect(lambda: self._open_matrix("initial"))
        initial_row = QHBoxLayout()
        initial_row.addWidget(self.initial_risk)
        initial_row.addWidget(self.initial_risk_matrix)
        form.addRow("Initial Risk", initial_row)

        self.control_text = QPlainTextEdit()
        self.control_text.setPlaceholderText("List specific controls; separate with commas")
        self.control_text.setMinimumHeight(64)
        form.addRow("Control(s)", self.control_text)

        self.residual_risk = QComboBox()
        self.residual_risk.addItems(service.RISK_LEVELS)
        self.residual_risk_matrix = QPushButton("Risk Matrix…")
        self.residual_risk_matrix.clicked.connect(lambda: self._open_matrix("residual"))
        residual_row = QHBoxLayout()
        residual_row.addWidget(self.residual_risk)
        residual_row.addWidget(self.residual_risk_matrix)
        form.addRow("Residual Risk", residual_row)

        self.implement_how = QLineEdit()
        self.implement_how.setPlaceholderText(
            "e.g., Covered in safety briefing; spotter assigned"
        )
        form.addRow("How to Implement", self.implement_how)

        self.implement_who = QLineEdit()
        self.implement_who.setPlaceholderText("e.g., Ops Officer / Team Leads")
        form.addRow("Who Will Implement", self.implement_who)

        button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, Qt.Horizontal, self
        )
        button_box.accepted.connect(self._attempt_save)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        if hazard:
            self._populate(hazard)

    def _populate(self, hazard: dict) -> None:
        self.sub_activity.setText(hazard.get("sub_activity", ""))
        self.hazard_outcome.setPlainText(hazard.get("hazard_outcome", ""))
        self.initial_risk.setCurrentText(hazard.get("initial_risk", "L"))
        self.control_text.setPlainText(hazard.get("control_text", ""))
        self.residual_risk.setCurrentText(hazard.get("residual_risk", "L"))
        self.implement_how.setText(hazard.get("implement_how", ""))
        self.implement_who.setText(hazard.get("implement_who", ""))

    def _open_matrix(self, target: str) -> None:
        dialog = RiskMatrixDialog(self)
        risk = dialog.exec_for(target)
        if risk:
            if target == "initial":
                self.initial_risk.setCurrentText(risk)
            else:
                self.residual_risk.setCurrentText(risk)

    def _attempt_save(self) -> None:
        errors = []
        sub_activity = self.sub_activity.text().strip()
        hazard_outcome = self.hazard_outcome.toPlainText().strip()
        control_text = self.control_text.toPlainText().strip()
        if not sub_activity:
            errors.append("Sub-Activity is required.")
        if not hazard_outcome:
            errors.append("Hazard / Outcome is required.")
        if not control_text:
            errors.append("Control(s) is required.")
        if errors:
            self._error_label.setText(" ".join(errors))
            self._error_label.show()
            QMessageBox.warning(self, "Validation", "\n".join(errors))
            return
        self._result = {
            "sub_activity": sub_activity,
            "hazard_outcome": hazard_outcome,
            "initial_risk": self.initial_risk.currentText(),
            "control_text": control_text,
            "residual_risk": self.residual_risk.currentText(),
            "implement_how": self.implement_how.text().strip() or None,
            "implement_who": self.implement_who.text().strip() or None,
        }
        self.accept()

    def result_payload(self) -> Optional[dict]:
        return self._result
