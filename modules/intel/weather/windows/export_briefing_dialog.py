"""Dialog for exporting weather briefing snippets."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..services.api_link import WeatherApiManager
from ..services.summary import build_weather_form_payload


class ExportBriefingDialog(QDialog):
    """Collects sections to include in a briefing export."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("exportBriefingDialog")
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowFlag(Qt.Window)
        self.setWindowTitle("Export Weather Briefing Snippet")
        self.resize(640, 480)
        self.api = WeatherApiManager.instance()
        self.api.dataUpdated.connect(self._handle_data)
        self._latest_payload: dict = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        checkbox_grid = QGridLayout()
        self.include_current = QCheckBox("Current", self)
        self.include_current.setChecked(True)
        self.include_current.toggled.connect(lambda _: self._handle_data({}))
        checkbox_grid.addWidget(self.include_current, 0, 0)
        self.include_forecast = QCheckBox("12h Forecast", self)
        self.include_forecast.setChecked(True)
        self.include_forecast.toggled.connect(lambda _: self._handle_data({}))
        checkbox_grid.addWidget(self.include_forecast, 0, 1)
        self.include_aviation = QCheckBox("Aviation", self)
        self.include_aviation.setChecked(True)
        self.include_aviation.toggled.connect(lambda _: self._handle_data({}))
        checkbox_grid.addWidget(self.include_aviation, 1, 0)
        self.include_alerts = QCheckBox("Alerts", self)
        self.include_alerts.setChecked(True)
        self.include_alerts.toggled.connect(lambda _: self._handle_data({}))
        checkbox_grid.addWidget(self.include_alerts, 1, 1)
        self.include_hwo = QCheckBox("HWO", self)
        self.include_hwo.setChecked(True)
        self.include_hwo.toggled.connect(lambda _: self._handle_data({}))
        checkbox_grid.addWidget(self.include_hwo, 2, 0)
        layout.addLayout(checkbox_grid)

        self.preview = QTextEdit(self)
        self.preview.setReadOnly(True)
        self.preview.setAccessibleName("Briefing Preview")
        layout.addWidget(self.preview)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Close | QDialogButtonBox.Ok, Qt.Horizontal, self
        )
        self.buttons.button(QDialogButtonBox.Ok).setText("Copy")
        self.buttons.button(QDialogButtonBox.Ok).clicked.connect(self._copy_text)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        QWidget.setTabOrder(self.include_current, self.include_forecast)
        QWidget.setTabOrder(self.include_forecast, self.include_aviation)
        QWidget.setTabOrder(self.include_aviation, self.include_alerts)
        QWidget.setTabOrder(self.include_alerts, self.include_hwo)
        QWidget.setTabOrder(self.include_hwo, self.preview)
        QWidget.setTabOrder(self.preview, self.buttons.button(QDialogButtonBox.Ok))

    def _handle_data(self, payload: dict) -> None:
        if payload:
            self._latest_payload = payload
        payload = self._latest_payload
        weather = build_weather_form_payload({"weather_payload": payload})
        parts = []
        if self.include_current.isChecked():
            current = weather.get("current", {}).get("local", "")
            parts.append(f"Current weather: {current or '—'}")
        if self.include_forecast.isChecked():
            forecast = weather.get("forecast", {}).get("local", "")
            parts.append(f"Next 12h: {forecast or '—'}")
        if self.include_aviation.isChecked():
            aviation = weather.get("current", {}).get("enroute", "") or weather.get("current", {}).get("local", "")
            parts.append(f"Aviation summary: {aviation or '—'}")
        if self.include_alerts.isChecked():
            alerts = weather.get("alerts", "")
            parts.append(f"Alerts: {alerts or '—'}")
        if self.include_hwo.isChecked():
            hwo = payload.get("hwo") or {}
            if isinstance(hwo, dict) and hwo.get("text"):
                text = str(hwo.get("text") or "").strip().replace("\r\n", "\n")
                excerpt = next((line.strip() for line in text.splitlines() if line.strip()), "")
                parts.append(f"HWO: {excerpt or '—'}")
            else:
                parts.append("HWO: —")
        self.preview.setPlainText("\n".join(parts))

    def _copy_text(self) -> None:
        self.preview.selectAll()
        self.preview.copy()


def show_window(parent: QWidget | None = None) -> ExportBriefingDialog:
    dialog = ExportBriefingDialog(parent)
    dialog.open()
    return dialog


__all__ = ["ExportBriefingDialog", "show_window"]
