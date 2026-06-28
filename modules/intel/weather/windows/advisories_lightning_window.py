"""Advisories and lightning monitoring window."""

from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services.api_link import WeatherApiManager
from ..services.settings import weather_settings
from utils.table_view_styles import apply_statusboard_table_behavior


class AdvisoriesLightningWindow(QMainWindow):
    """Displays advisories and lightning strike information."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("advisoriesLightningWindow")
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowTitle("Advisories & Lightning")
        self.resize(1100, 700)
        self.api = WeatherApiManager.instance()
        self.api.alertsUpdated.connect(self._handle_advisories)
        self.api.lightningUpdated.connect(self._handle_lightning)
        self._setup_ui()
        self._load_state()

    def _setup_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Location", central))
        self.location_input = QLineEdit(central)
        controls.addWidget(self.location_input)
        controls.addWidget(QLabel("Radius (nm)", central))
        self.radius_input = QComboBox(central)
        self.radius_input.addItems(["25", "50", "75"])
        controls.addWidget(self.radius_input)
        self.threshold_button = QPushButton("Alert Thresholds", central)
        controls.addWidget(self.threshold_button)
        self.refresh_button = QPushButton("Refresh", central)
        self.refresh_button.clicked.connect(self.api.refresh_all)
        controls.addWidget(self.refresh_button)
        controls.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        layout.addLayout(controls)

        splitter = QSplitter(Qt.Horizontal, central)
        self.advisories_table = QTableWidget(0, 4, splitter)
        self.advisories_table.setHorizontalHeaderLabels(
            ["Type", "Start", "End", "Headline"]
        )
        apply_statusboard_table_behavior(self.advisories_table, stretch_last_section=True)
        self.lightning_table = QTableWidget(0, 3, splitter)
        self.lightning_table.setHorizontalHeaderLabels(["Time", "Lat", "Lon"])
        apply_statusboard_table_behavior(self.lightning_table, stretch_last_section=True)
        splitter.addWidget(self.advisories_table)
        splitter.addWidget(self.lightning_table)
        layout.addWidget(splitter)

        self.notifications_toggle = QCheckBox("Desktop notification on new strikes", central)
        layout.addWidget(self.notifications_toggle)

        self.setCentralWidget(central)
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        QWidget.setTabOrder(self.location_input, self.radius_input)
        QWidget.setTabOrder(self.radius_input, self.threshold_button)
        QWidget.setTabOrder(self.threshold_button, self.refresh_button)
        QWidget.setTabOrder(self.refresh_button, self.advisories_table)

    def _handle_advisories(self, advisories: List[dict] | List[object]) -> None:
        self.advisories_table.setRowCount(0)
        for advisory in advisories:
            row = self.advisories_table.rowCount()
            self.advisories_table.insertRow(row)
            event = getattr(advisory, "event", None)
            headline = getattr(advisory, "headline", None)
            start = getattr(advisory, "start", None)
            end = getattr(advisory, "end", None)
            if isinstance(advisory, dict):
                event = event or advisory.get("event")
                headline = headline or advisory.get("headline")
                start = start or advisory.get("start")
                end = end or advisory.get("end")
            self.advisories_table.setItem(row, 0, QTableWidgetItem(event or "Advisory"))
            self.advisories_table.setItem(row, 1, QTableWidgetItem(str(start or "—")))
            self.advisories_table.setItem(row, 2, QTableWidgetItem(str(end or "—")))
            self.advisories_table.setItem(row, 3, QTableWidgetItem(headline or "—"))
        self.status_bar.showMessage(f"Loaded {len(advisories)} advisories")

    def _handle_lightning(self, strikes: List[dict] | List[object]) -> None:
        self.lightning_table.setRowCount(0)
        for strike in strikes:
            row = self.lightning_table.rowCount()
            self.lightning_table.insertRow(row)
            time = getattr(strike, "timestamp", None)
            lat = getattr(strike, "latitude", None)
            lon = getattr(strike, "longitude", None)
            if isinstance(strike, dict):
                time = time or strike.get("timestamp")
                lat = lat or strike.get("latitude")
                lon = lon or strike.get("longitude")
            self.lightning_table.setItem(row, 0, QTableWidgetItem(str(time or "—")))
            self.lightning_table.setItem(row, 1, QTableWidgetItem(str(lat or "—")))
            self.lightning_table.setItem(row, 2, QTableWidgetItem(str(lon or "—")))
        self.status_bar.showMessage(f"Loaded {len(strikes)} lightning strikes")

    def _load_state(self) -> None:
        geometry = weather_settings().value("geom/AdvisoriesLightningWindow")
        if geometry:
            self.restoreGeometry(geometry)

    def closeEvent(self, event) -> None:  # noqa: D401
        weather_settings().set_value("geom/AdvisoriesLightningWindow", self.saveGeometry())
        super().closeEvent(event)


def show_window() -> AdvisoriesLightningWindow:
    window = AdvisoriesLightningWindow()
    window.show()
    window.raise_()
    return window


__all__ = ["AdvisoriesLightningWindow", "show_window"]
