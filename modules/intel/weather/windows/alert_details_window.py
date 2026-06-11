"""Detailed alert window for viewing NWS products."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..services.api_link import WeatherApiManager
from ..services.settings import weather_settings


class AlertDetailsWindow(QMainWindow):
    """Displays detailed information about a weather alert."""

    def __init__(self, payload: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("alertDetailsWindow")
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowFlag(Qt.Window)
        self.setWindowTitle("Alert Details")
        self.resize(900, 700)
        self._payload = payload or {}
        self.api = WeatherApiManager.instance()
        self.api.alertsUpdated.connect(self._alerts_updated)
        self._setup_ui()
        self._load_state()
        self._bind_payload(self._payload)

    def _setup_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_layout = QHBoxLayout()
        self.title_label = QLabel("Alert", central)
        self.title_label.setAccessibleName("Alert Title")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(self.title_label)
        header_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.severity_label = QLabel("Severity: —", central)
        self.severity_label.setAccessibleName("Alert Severity")
        header_layout.addWidget(self.severity_label)
        layout.addLayout(header_layout)

        self.tabs = QTabWidget(central)
        self.tabs.setAccessibleName("Alert Detail Tabs")

        summary_tab = QWidget(self.tabs)
        summary_layout = QVBoxLayout(summary_tab)
        self.summary_text = QTextEdit(summary_tab)
        self.summary_text.setReadOnly(True)
        self.summary_text.setAccessibleName("Summary Text")
        summary_layout.addWidget(self.summary_text)
        self.tabs.addTab(summary_tab, "Summary")

        full_text_tab = QWidget(self.tabs)
        full_layout = QVBoxLayout(full_text_tab)
        self.full_text = QTextEdit(full_text_tab)
        self.full_text.setReadOnly(True)
        self.full_text.setAccessibleName("Full Text")
        full_layout.addWidget(self.full_text)
        self.tabs.addTab(full_text_tab, "Full Text")

        areas_tab = QWidget(self.tabs)
        areas_layout = QVBoxLayout(areas_tab)
        self.areas_text = QTextEdit(areas_tab)
        self.areas_text.setReadOnly(True)
        self.areas_text.setAccessibleName("Affected Areas")
        areas_layout.addWidget(self.areas_text)
        self.tabs.addTab(areas_tab, "Areas")

        layout.addWidget(self.tabs)

        action_row = QHBoxLayout()
        self.ack_button = QPushButton("Acknowledge", central)
        self.ack_button.clicked.connect(self._acknowledge)
        action_row.addWidget(self.ack_button)
        self.copy_button = QPushButton("Copy Full Text", central)
        self.copy_button.clicked.connect(self._copy_text)
        action_row.addWidget(self.copy_button)
        self.close_button = QPushButton("Close", central)
        self.close_button.clicked.connect(self.close)
        action_row.addWidget(self.close_button)
        action_row.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        layout.addLayout(action_row)

        self.setCentralWidget(central)
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        # TAB_ORDER: tabs -> acknowledge -> copy -> close
        QWidget.setTabOrder(self.tabs, self.ack_button)
        QWidget.setTabOrder(self.ack_button, self.copy_button)
        QWidget.setTabOrder(self.copy_button, self.close_button)

    def _acknowledge(self) -> None:
        # TODO: integrate acknowledgement persistence
        self.status_bar.showMessage("Alert acknowledged")

    def _copy_text(self) -> None:
        self.full_text.selectAll()
        self.full_text.copy()

    def _bind_payload(self, payload: dict) -> None:
        self.title_label.setText(payload.get("event", "Alert"))
        self.severity_label.setText(f"Severity: {payload.get('severity', '—')}")
        self.summary_text.setPlainText(payload.get("description", ""))
        self.full_text.setPlainText(payload.get("full_text", ""))
        areas = payload.get("areas", [])
        self.areas_text.setPlainText("\n".join(areas) if areas else "No area data available.")
        self.status_bar.showMessage(payload.get("timing", "Issued: —"))

    def _alerts_updated(self, advisories: list[dict]) -> None:
        if not self._payload:
            return
        for advisory in advisories:
            if advisory.get("event") == self._payload.get("event"):
                self._payload = advisory
                self._bind_payload(advisory)
                break

    def _load_state(self) -> None:
        settings_store = weather_settings()
        geometry = settings_store.value("geom/AlertDetailsWindow")
        if geometry:
            self.restoreGeometry(geometry)

    def closeEvent(self, event) -> None:  # noqa: D401
        settings_store = weather_settings()
        settings_store.set_value("geom/AlertDetailsWindow", self.saveGeometry())
        super().closeEvent(event)


def show_window(payload: dict | None = None) -> AlertDetailsWindow:
    window = AlertDetailsWindow(payload or {})
    window.show()
    window.raise_()
    return window


__all__ = ["AlertDetailsWindow", "show_window"]
