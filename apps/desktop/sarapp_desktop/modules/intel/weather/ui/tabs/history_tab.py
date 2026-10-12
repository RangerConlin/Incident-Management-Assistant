"""History tab — trend chart fed from weather_history, since NWS provides
no historical-observation endpoint (samples accumulate going forward only)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ...models.location import WeatherLocation
from ...services import weather_repository_client as client
from ...services.weather_manager import WeatherManager
from ..widgets.trend_chart_widget import TrendChartWidget

_RANGES = {
    "Last 24 hours": 24,
    "Last 72 hours": 72,
    "Last 7 days": 24 * 7,
}

_SAMPLE_METRICS = (
    "temperature_f",
    "wind_gust_kt",
    "relative_humidity_pct",
    "barometric_pressure_hpa",
    "visibility_sm",
)


class HistoryTab(QWidget):
    def __init__(self, manager: WeatherManager, incident_id: str, parent=None):
        super().__init__(parent)
        self._manager = manager
        self._incident_id = incident_id
        self._location: Optional[WeatherLocation] = None

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Range"))
        self._range_combo = QComboBox()
        self._range_combo.addItems(list(_RANGES.keys()))
        self._range_combo.currentTextChanged.connect(lambda _t: self._reload())
        toolbar.addWidget(self._range_combo)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self._chart = TrendChartWidget()
        layout.addWidget(self._chart, 1)

        self._note = QLabel("")
        self._note.setStyleSheet("color: rgba(128,128,128,0.9); font-size: 10.5px;")
        self._note.setWordWrap(True)
        layout.addWidget(self._note)

    def set_location(self, location: Optional[WeatherLocation]) -> None:
        self._location = location
        self._reload()

    def _reload(self) -> None:
        if self._location is None:
            return
        hours = _RANGES[self._range_combo.currentText()]
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds")
        try:
            result = client.get_history(self._incident_id, self._location.location_id, since=since)
        except Exception:
            result = {"samples": []}
        samples = result.get("samples", [])
        if not samples:
            self._note.setText("No history recorded yet for this location. History begins once polling starts.")
            self._chart.clear()
            return

        times = [self._parse_time(s.get("recorded_at")) for s in samples]
        for metric in _SAMPLE_METRICS:
            values = [s.get(metric) for s in samples]
            self._chart.set_series(metric, times, values, visible=metric in ("temperature_f", "wind_gust_kt"))

        first_time = samples[0].get("recorded_at", "")
        self._note.setText(
            f"History begins {first_time} — recorded on each poll going forward; "
            "NWS provides no retroactive backfill."
        )

    @staticmethod
    def _parse_time(value) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)


__all__ = ["HistoryTab"]
