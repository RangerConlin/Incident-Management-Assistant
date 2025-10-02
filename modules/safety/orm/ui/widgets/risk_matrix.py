"""Risk matrix dialog for selecting CAP risk levels."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ... import service

SEVERITY_LABELS = [
    ("A", "Catastrophic"),
    ("B", "Critical"),
    ("C", "Moderate"),
    ("D", "Negligible"),
]

LIKELIHOOD_LABELS = [
    ("I", "Frequent"),
    ("II", "Likely"),
    ("III", "Occasional"),
    ("IV", "Seldom"),
    ("V", "Unlikely"),
]


class RiskMatrixDialog(QDialog):
    """Modal dialog that allows choosing a risk cell from CAP matrix."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CAP Risk Matrix")
        self.setModal(True)
        self.selected_severity = "C"
        self.selected_likelihood = "III"
        self._target: Optional[str] = None
        self.selected_risk: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Select severity (rows) and likelihood (columns) to compute the risk level."
            )
        )

        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        layout.addLayout(grid)

        # Column headers
        for col, (_, label) in enumerate(LIKELIHOOD_LABELS, start=1):
            header = QLabel(label)
            header.setAlignment(Qt.AlignCenter)
            header.setStyleSheet("font-weight: 600;")
            grid.addWidget(header, 0, col)

        # Row headers and cells
        self._buttons: dict[tuple[str, str], QPushButton] = {}
        for row, (severity_code, severity_label) in enumerate(SEVERITY_LABELS, start=1):
            header = QLabel(f"{severity_code} — {severity_label}")
            header.setStyleSheet("font-weight: 600;")
            grid.addWidget(header, row, 0)
            for col, (likelihood_code, _) in enumerate(LIKELIHOOD_LABELS, start=1):
                risk = service.risk_from(severity_code, likelihood_code)
                btn = QPushButton(risk)
                btn.setCheckable(True)
                btn.setMinimumSize(72, 48)
                btn.clicked.connect(
                    lambda _=False, s=severity_code, l=likelihood_code: self._select_cell(s, l)
                )
                self._buttons[(severity_code, likelihood_code)] = btn
                grid.addWidget(btn, row, col)

        self._select_cell(self.selected_severity, self.selected_likelihood)

        button_box = QDialogButtonBox()
        self.apply_initial = button_box.addButton(
            "Apply to Initial", QDialogButtonBox.AcceptRole
        )
        self.apply_residual = button_box.addButton(
            "Apply to Residual", QDialogButtonBox.AcceptRole
        )
        cancel_btn = button_box.addButton(QDialogButtonBox.Cancel)
        self.apply_initial.clicked.connect(lambda: self._accept("initial"))
        self.apply_residual.clicked.connect(lambda: self._accept("residual"))
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(button_box)

    def _select_cell(self, severity: str, likelihood: str) -> None:
        self.selected_severity = severity
        self.selected_likelihood = likelihood
        for (sev, like), btn in self._buttons.items():
            btn.setChecked(sev == severity and like == likelihood)
            if btn.isChecked():
                btn.setStyleSheet("background-color: #2d89ef; color: white; font-weight: 600;")
            else:
                btn.setStyleSheet("")
        self.selected_risk = service.risk_from(severity, likelihood)

    def _accept(self, target: str) -> None:
        self._target = target
        if self.selected_risk is None:
            self.selected_risk = service.risk_from(
                self.selected_severity, self.selected_likelihood
            )
        self.accept()

    def exec_for(self, target: str) -> Optional[str]:
        self._target = target
        if self.exec() == QDialog.Accepted:
            return self.selected_risk
        return None

    def target(self) -> Optional[str]:
        return self._target
