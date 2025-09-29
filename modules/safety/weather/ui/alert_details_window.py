from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QWidget,
    QFormLayout,
    QCheckBox,
    QPlainTextEdit,
    QListWidget,
    QDialogButtonBox,
)

from ._geometry import GeometryHelper


class AlertDetailsWindow(QDialog):
    acknowledge = Signal()
    copyHeadline = Signal()
    copyFullText = Signal()

    def __init__(self, event: str, severity: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Alert Details — {event}")
        GeometryHelper.restore(self, "AlertDetailsWindow")
        self._build_ui(event, severity)

    def closeEvent(self, e):
        GeometryHelper.save(self, "AlertDetailsWindow")
        super().closeEvent(e)

    def _build_ui(self, event: str, severity: str) -> None:
        v = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel(event))
        chip = QLabel(severity); chip.setStyleSheet("QLabel{border-radius:10px; padding:2px 8px; background:#ffcdd2;}")
        header.addStretch(1); header.addWidget(chip)
        v.addLayout(header)

        tabs = QTabWidget(self)
        # Summary
        w_sum = QWidget(); f = QFormLayout(w_sum)
        f.addRow("Severity:", QLabel(severity))
        f.addRow("Certainty:", QLabel("—"))
        f.addRow("Urgency:", QLabel("—"))
        f.addRow("Effective:", QLabel("—"))
        f.addRow("Expires:", QLabel("—"))
        # Full text
        w_full = QWidget(); v2 = QVBoxLayout(w_full)
        self.chkMono = QCheckBox("Monospace")
        self.txtFull = QPlainTextEdit(); self.txtFull.setReadOnly(True)
        v2.addWidget(self.chkMono); v2.addWidget(self.txtFull)
        self.chkMono.toggled.connect(lambda on: self.txtFull.setStyleSheet("font-family:monospace;" if on else ""))
        # Areas
        w_areas = QWidget(); v3 = QVBoxLayout(w_areas)
        self.listAreas = QListWidget();
        v3.addWidget(self.listAreas)
        v3.addWidget(QLabel("Map polygon preview (GIS module will render)"))

        tabs.addTab(w_sum, "Summary"); tabs.addTab(w_full, "Full Text"); tabs.addTab(w_areas, "Areas")
        v.addWidget(tabs)

        buttons = QDialogButtonBox()
        btnAck = buttons.addButton("Acknowledge", QDialogButtonBox.ActionRole)
        btnCopyH = buttons.addButton("Copy Headline", QDialogButtonBox.ActionRole)
        btnCopyF = buttons.addButton("Copy Full Text", QDialogButtonBox.ActionRole)
        btnClose = buttons.addButton(QDialogButtonBox.Close)
        v.addWidget(buttons)
        btnAck.clicked.connect(self.acknowledge)
        btnCopyH.clicked.connect(self.copyHeadline)
        btnCopyF.clicked.connect(self.copyFullText)
        btnClose.clicked.connect(self.close)

