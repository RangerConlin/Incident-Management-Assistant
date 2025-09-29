from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
    QFrame,
    QSplitter,
    QTabWidget,
    QToolButton,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QProgressBar,
    QFormLayout,
    QPlainTextEdit,
)


class WeatherSummaryPanel(QWidget):
    refreshRequested = Signal()
    overrideLocationRequested = Signal()
    openAviationWindowRequested = Signal(str)
    exportSnippetRequested = Signal()
    timelineRequested = Signal()
    settingsRequested = Signal()
    alertDetailsRequested = Signal(str)
    alertAcknowledgeRequested = Signal(str)
    autoLogToggled = Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _card(self, title: str) -> QFrame:
        box = QFrame(self)
        box.setObjectName("SectionBox")
        v = QVBoxLayout(box)
        h = QHBoxLayout()
        lbl = QLabel(title)
        lbl.setStyleSheet("font-weight:600; font-size: 14px;")
        h.addWidget(lbl)
        h.addStretch(1)
        v.addLayout(h)
        return box

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # Header
        header = QHBoxLayout()
        title = QLabel("Weather Safety")
        title.setStyleSheet("font-size:18px; font-weight:600;")
        self.lblLocation = QLabel("ICP: —, —")
        self.btnOverride = QPushButton("Override…")
        self.btnOverride.setAccessibleName("Override Location")
        self.btnRefresh = QPushButton("Refresh")
        self.lblUpdated = QLabel("Updated: —")
        self.progress = QProgressBar()
        self.progress.setMaximumHeight(10)
        self.progress.setRange(0, 0)
        self.progress.hide()

        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.lblLocation)
        header.addWidget(self.btnOverride)
        header.addSpacing(16)
        header.addWidget(self.btnRefresh)
        header.addWidget(self.lblUpdated)
        root.addLayout(header)
        root.addWidget(self.progress)

        # Body columns
        split = QSplitter(Qt.Horizontal, self)

        # Column A – Current Conditions
        colA = self._card("Current Conditions")
        a_layout = colA.layout()  # type: ignore
        grid = QFormLayout()
        self.lblTemp = QLabel("—")
        self.lblFeels = QLabel("—")
        self.lblWind = QLabel("—")
        self.lblVis = QLabel("—")
        self.lblCloud = QLabel("—")
        self.lblHum = QLabel("—")
        self.lblPress = QLabel("—")
        grid.addRow("Temperature:", self.lblTemp)
        grid.addRow("Feels Like:", self.lblFeels)
        grid.addRow("Wind:", self.lblWind)
        grid.addRow("Visibility:", self.lblVis)
        grid.addRow("Cloud Cover:", self.lblCloud)
        grid.addRow("Humidity:", self.lblHum)
        grid.addRow("Pressure:", self.lblPress)
        a_layout.addLayout(grid)

        # Column B – 3‑Day Forecast
        colB = self._card("3-Day Forecast")
        b_layout = colB.layout()  # type: ignore
        self.listForecast = QListWidget()
        self.listForecast.setSelectionMode(QAbstractItemView.NoSelection)
        b_layout.addWidget(self.listForecast)

        # Column C – Aviation Summary
        colC = self._card("Aviation Summary")
        c_layout = colC.layout()  # type: ignore
        station_row = QHBoxLayout()
        self.comboStation = QComboBox(); self.comboStation.setEditable(True)
        self.btnFav = QToolButton(); self.btnFav.setText("★"); self.btnFav.setToolTip("Add to Favorites")
        station_row.addWidget(QLabel("Station:"))
        station_row.addWidget(self.comboStation)
        station_row.addWidget(self.btnFav)
        c_layout.addLayout(station_row)

        self.tabsAv = QTabWidget()
        self.tabsAv.setDocumentMode(True)
        # METAR tab
        w_metar = QWidget(); v1 = QVBoxLayout(w_metar)
        self.chkDecoded_metar = QCheckBox("Decoded")
        h1 = QHBoxLayout(); self.btnCopyMetar = QPushButton("Copy"); self.btnOpenAvWin1 = QPushButton("Open Aviation Window")
        h1.addWidget(self.chkDecoded_metar); h1.addStretch(1); h1.addWidget(self.btnCopyMetar); h1.addWidget(self.btnOpenAvWin1)
        self.txtMetar = QPlainTextEdit(); self.txtMetar.setReadOnly(True)
        v1.addLayout(h1); v1.addWidget(self.txtMetar)
        # TAF tab
        w_taf = QWidget(); v2 = QVBoxLayout(w_taf)
        self.chkDecoded_taf = QCheckBox("Decoded")
        h2 = QHBoxLayout(); self.btnCopyTaf = QPushButton("Copy"); self.btnOpenAvWin2 = QPushButton("Open Aviation Window")
        h2.addWidget(self.chkDecoded_taf); h2.addStretch(1); h2.addWidget(self.btnCopyTaf); h2.addWidget(self.btnOpenAvWin2)
        self.txtTaf = QPlainTextEdit(); self.txtTaf.setReadOnly(True)
        v2.addLayout(h2); v2.addWidget(self.txtTaf)

        self.tabsAv.addTab(w_metar, "METAR")
        self.tabsAv.addTab(w_taf, "TAF")
        c_layout.addWidget(self.tabsAv)

        split.addWidget(colA); split.addWidget(colB); split.addWidget(colC)
        split.setSizes([300, 400, 360])
        root.addWidget(split)

        # Alerts Section
        alerts_box = self._card("Active Alerts")
        al = alerts_box.layout()  # type: ignore
        self.tblAlerts = QTableWidget(0, 5, self)
        self.tblAlerts.setHorizontalHeaderLabels(["Severity", "Headline", "Valid", "Area", "Actions"])
        self.tblAlerts.setSelectionMode(QAbstractItemView.NoSelection)
        al.addWidget(self.tblAlerts)
        self.chkAutoLog = QCheckBox("Auto-log severe alerts to Safety Notes")
        al.addWidget(self.chkAutoLog)
        root.addWidget(alerts_box)

        # HWO Section
        hwo_box = self._card("Hazardous Weather Outlook")
        hl = hwo_box.layout()  # type: ignore
        self.txtHwo = QPlainTextEdit(); self.txtHwo.setReadOnly(True)
        btnRow = QHBoxLayout(); self.btnOpenHwo = QPushButton("Open Full Outlook"); btnRow.addStretch(1); btnRow.addWidget(self.btnOpenHwo)
        hl.addWidget(self.txtHwo); hl.addLayout(btnRow)
        root.addWidget(hwo_box)

        # Footer buttons
        footer = QHBoxLayout()
        self.btnTimeline = QPushButton("Timeline View")
        self.btnSettings = QPushButton("Settings")
        self.btnExport = QPushButton("Export Snippet")
        footer.addStretch(1)
        footer.addWidget(self.btnTimeline)
        footer.addWidget(self.btnSettings)
        footer.addWidget(self.btnExport)
        root.addLayout(footer)

        # Accessibility & keyboard
        self.btnRefresh.setShortcut(QKeySequence.Refresh)
        QShortcut(QKeySequence("Ctrl+C"), self, activated=self._copy_visible_text)

        # Wire signals to UI-only controller slots
        self.btnRefresh.clicked.connect(self.refreshRequested)
        self.btnOverride.clicked.connect(self.overrideLocationRequested)
        self.btnCopyMetar.clicked.connect(lambda: self._copy_text(self.txtMetar))
        self.btnCopyTaf.clicked.connect(lambda: self._copy_text(self.txtTaf))
        self.btnOpenAvWin1.clicked.connect(self._emit_open_av)
        self.btnOpenAvWin2.clicked.connect(self._emit_open_av)
        self.btnExport.clicked.connect(self.exportSnippetRequested)
        self.btnTimeline.clicked.connect(self.timelineRequested)
        self.btnSettings.clicked.connect(self.settingsRequested)
        self.chkAutoLog.toggled.connect(self.autoLogToggled)

    def _emit_open_av(self) -> None:
        station = self.comboStation.currentText().strip()
        if station:
            self.openAviationWindowRequested.emit(station)

    def _copy_text(self, widget: QPlainTextEdit) -> None:
        try:
            from PySide6.QtWidgets import QApplication

            QApplication.clipboard().setText(widget.toPlainText())
        except Exception:
            pass

    def _copy_visible_text(self) -> None:
        page = self.tabsAv.currentWidget()
        if page is not None:
            edit = page.findChild(QPlainTextEdit)
            if edit:
                self._copy_text(edit)


def get_weather_panel(parent=None) -> WeatherSummaryPanel:
    return WeatherSummaryPanel(parent=parent)

