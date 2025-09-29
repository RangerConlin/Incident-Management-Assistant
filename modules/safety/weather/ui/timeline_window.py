from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow,
    QToolBar,
    QLabel,
    QComboBox,
    QCheckBox,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
)
from PySide6.QtCore import Qt

from ._geometry import GeometryHelper


class WeatherTimelineWindow(QMainWindow):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Weather Timeline")
        GeometryHelper.restore(self, "WeatherTimelineWindow")
        tb = QToolBar("Toolbar", self); self.addToolBar(tb)
        self.comboRange = QComboBox(); self.comboRange.addItems(["Now", "24h", "48h", "72h"]) ; tb.addWidget(QLabel("Range:")); tb.addWidget(self.comboRange)
        tb.addSeparator()
        self.chkTemp = QCheckBox("Temp"); self.chkWind = QCheckBox("Wind"); self.chkPrecip = QCheckBox("Precip"); self.chkVis = QCheckBox("Visibility"); self.chkSun = QCheckBox("Sunrise/Sunset")
        for w in (self.chkTemp, self.chkWind, self.chkPrecip, self.chkVis, self.chkSun):
            w.setChecked(True); tb.addWidget(w)
        tb.addSeparator(); self.lblLoc = QLabel("—, —"); tb.addWidget(self.lblLoc)
        central = QWidget(); v = QVBoxLayout(central)
        self.chartPlaceholder = QLabel("[Timeline chart placeholder]"); self.chartPlaceholder.setAlignment(Qt.AlignCenter); self.chartPlaceholder.setMinimumHeight(240)
        v.addWidget(self.chartPlaceholder)
        self.insight = QLabel("Insight strip: annotated notes here")
        v.addWidget(self.insight)
        foot = QHBoxLayout(); self.btnCopyImg = QPushButton("Copy as Image"); self.btnCopyTxt = QPushButton("Copy Text Summary"); self.btnAddNote = QPushButton("Add Note to Safety"); self.btnClose = QPushButton("Close"); foot.addStretch(1); foot.addWidget(self.btnCopyImg); foot.addWidget(self.btnCopyTxt); foot.addWidget(self.btnAddNote); foot.addWidget(self.btnClose)
        v.addLayout(foot); self.setCentralWidget(central)
        self.btnClose.clicked.connect(self.close)

    def closeEvent(self, e):
        GeometryHelper.save(self, "WeatherTimelineWindow")
        super().closeEvent(e)

