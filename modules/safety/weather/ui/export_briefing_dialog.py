from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QGroupBox,
    QVBoxLayout as QV,
    QCheckBox,
    QPlainTextEdit,
    QDialogButtonBox,
)


class ExportBriefingSnippetDialog(QDialog):
    copyRequested = Signal()
    insertRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Weather Briefing Snippet")
        self.setModal(True)
        v = QVBoxLayout(self)
        opts = QGroupBox("Include"); lo = QV(opts)
        self.chkCurrent = QCheckBox("Current Conditions"); self.chk12h = QCheckBox("Next 12h"); self.chkAv = QCheckBox("Aviation Summary"); self.chkAlerts = QCheckBox("Active Alerts"); self.chkHwo = QCheckBox("HWO excerpt")
        for w in (self.chkCurrent, self.chk12h, self.chkAv, self.chkAlerts, self.chkHwo): w.setChecked(True); lo.addWidget(w)
        v.addWidget(opts)
        self.txtPreview = QPlainTextEdit(); self.txtPreview.setReadOnly(True); self.txtPreview.setStyleSheet("font-family:monospace;")
        v.addWidget(self.txtPreview)
        buttons = QDialogButtonBox()
        btnCopy = buttons.addButton("Copy to Clipboard", QDialogButtonBox.ActionRole)
        btnInsert = buttons.addButton("Insert into Debrief", QDialogButtonBox.ActionRole)
        btnClose = buttons.addButton(QDialogButtonBox.Close)
        v.addWidget(buttons)
        btnCopy.clicked.connect(self.copyRequested)
        btnInsert.clicked.connect(self.insertRequested)
        btnClose.clicked.connect(self.close)
        QShortcut(QKeySequence("Esc"), self, activated=self.reject)

