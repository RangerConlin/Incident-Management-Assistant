from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QCheckBox


class AlertPopup(QDialog):
    acknowledge = Signal()
    openDetails = Signal()
    mute30m = Signal(bool)
    soundToggled = Signal(bool)

    def __init__(self, title: str, body: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Weather Alert")
        self.setWindowFlag(Qt.Tool)
        self.setWindowModality(Qt.NonModal)
        self._drag_pos = None
        self._build_ui(title, body)

    def _build_ui(self, title: str, body: str) -> None:
        v = QVBoxLayout(self)
        lblTitle = QLabel(title)
        lblTitle.setStyleSheet("font-weight:600; font-size:14px;")
        v.addWidget(lblTitle)
        v.addWidget(QLabel(body))
        row = QHBoxLayout()
        btnAck = QPushButton("Acknowledge"); btnOpen = QPushButton("Open Details")
        btnMute = QPushButton("Mute 30m")
        self.chkSound = QCheckBox("Sound ON")
        self.chkSound.setChecked(True)
        row.addWidget(btnAck); row.addWidget(btnOpen); row.addWidget(btnMute); row.addWidget(self.chkSound)
        v.addLayout(row)
        btnAck.clicked.connect(self.acknowledge)
        btnOpen.clicked.connect(self.openDetails)
        btnMute.clicked.connect(lambda: self.mute30m.emit(True))
        self.chkSound.toggled.connect(self.soundToggled)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint()
            e.accept()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_pos is not None:
            delta = e.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = e.globalPosition().toPoint()
            e.accept()
        super().mouseMoveEvent(e)

