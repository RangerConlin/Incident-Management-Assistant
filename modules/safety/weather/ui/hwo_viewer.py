from __future__ import annotations

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QPlainTextEdit

from ._geometry import GeometryHelper


class HWOViewerWindow(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Hazardous Weather Outlook")
        GeometryHelper.restore(self, "HWOViewerWindow")
        v = QVBoxLayout(self)
        top = QHBoxLayout(); self.lblOffice = QLabel("WFO —"); top.addWidget(QLabel("Hazardous Weather Outlook")); top.addStretch(1); top.addWidget(self.lblOffice); v.addLayout(top)
        self.txt = QPlainTextEdit(); self.txt.setReadOnly(True)
        v.addWidget(self.txt)
        toolbar = QHBoxLayout()
        self.btnCopy = QPushButton("Copy")
        self.btnFind = QPushButton("Find (Ctrl+F)")
        self.btnOpenBrowser = QPushButton("Open in Browser")
        self.btnClose = QPushButton("Close")
        toolbar.addWidget(self.btnCopy); toolbar.addWidget(self.btnFind); toolbar.addStretch(1); toolbar.addWidget(self.btnOpenBrowser); toolbar.addWidget(self.btnClose)
        v.addLayout(toolbar)
        self.btnClose.clicked.connect(self.close)
        QShortcut(QKeySequence.Find, self, activated=self._focus_find)

    def closeEvent(self, e):
        GeometryHelper.save(self, "HWOViewerWindow")
        super().closeEvent(e)

    def _focus_find(self) -> None:
        self.txt.setFocus()

