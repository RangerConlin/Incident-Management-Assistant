from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow,
    QToolBar,
    QLabel,
    QComboBox,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QCheckBox,
    QPushButton,
    QPlainTextEdit,
)

from ._geometry import GeometryHelper


class AviationWeatherWindow(QMainWindow):
    newPanelRequested = Signal()
    saveToLogRequested = Signal(str)
    addToBriefingRequested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Aviation Weather")
        GeometryHelper.restore(self, "AviationWeatherWindow")
        self._build_ui()

    def closeEvent(self, e):
        GeometryHelper.save(self, "AviationWeatherWindow")
        super().closeEvent(e)

    def _build_ui(self) -> None:
        tb = QToolBar("Top", self)
        self.addToolBar(tb)
        self.btnAdd = QAction("+ Add", self); tb.addAction(self.btnAdd)
        self.btnSettings = QAction("Settings", self); tb.addAction(self.btnSettings)
        tb.addSeparator()
        tb.addWidget(QLabel("Layout:"))
        self.comboLayout = QComboBox(); self.comboLayout.addItems(["Tabs", "2-Up", "4-Up"]) ; tb.addWidget(self.comboLayout)
        tb.addSeparator()
        tb.addWidget(QLabel("Auto-refresh:")); self.comboRefresh = QComboBox(); self.comboRefresh.addItems(["Off", "1 min", "5 min", "10 min"]) ; tb.addWidget(self.comboRefresh)
        self.btnPin = QAction("Pin", self); self.btnPin.setCheckable(True); tb.addAction(self.btnPin)

        self.tabs = QTabWidget(self)
        self.tabs.setDocumentMode(True)
        self.setCentralWidget(self.tabs)

        # Starter empty state
        empty = QWidget(); v = QVBoxLayout(empty); msg = QLabel("No station selected — use + Add to choose one."); msg.setAlignment(Qt.AlignCenter); v.addWidget(msg)
        self.tabs.addTab(empty, "Welcome")

        # Shortcuts
        QShortcut(QKeySequence("Ctrl+T"), self, activated=self._new_tab)
        QShortcut(QKeySequence("Ctrl+W"), self, activated=self._close_current)
        QShortcut(QKeySequence("Ctrl+D"), self, activated=self._toggle_decoded)

    def _new_tab(self) -> None:
        page = QWidget(); v = QVBoxLayout(page)
        h = QHBoxLayout(); self.chkDecoded = QCheckBox("Decoded");
        btnCopy = QPushButton("Copy"); btnSave = QPushButton("Save to Incident Log"); btnBrief = QPushButton("Add to Briefing"); btnPop = QPushButton("Pop-out")
        h.addWidget(self.chkDecoded); h.addStretch(1); h.addWidget(btnCopy); h.addWidget(btnSave); h.addWidget(btnBrief); h.addWidget(btnPop)
        txt = QPlainTextEdit(); txt.setReadOnly(True)
        v.addLayout(h); v.addWidget(txt)
        idx = self.tabs.addTab(page, "Station")
        self.tabs.setCurrentIndex(idx)

    def _close_current(self) -> None:
        i = self.tabs.currentIndex()
        if i > -1:
            self.tabs.removeTab(i)

    def _toggle_decoded(self) -> None:
        # UI-only placeholder
        pass

