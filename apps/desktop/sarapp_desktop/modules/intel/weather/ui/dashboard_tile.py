"""Weather dashboard tile — the ADS-grid at-a-glance widget.

Replaces the old `ui.widgets.components.WeatherWidget`. Read-only/
presentational: all data comes from `WeatherManager` signals/getters, no
direct network or Mongo access here.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QWidget

from ui.widgets.components import LiveWidget
from utils.incident_context import get_active_incident_id
from utils.styles import subscribe_theme, weather_severity_colors

from ..services.weather_manager import get_weather_manager


class WeatherDashboardTile(LiveWidget):
    """Compact at-a-glance weather tile; click opens the full detail panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self._manager = None
        self._incident_id: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        self._location_label = QLabel("Weather")
        self._location_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        top_row.addWidget(self._location_label, 1)
        self._severity_badge = QLabel("")
        self._severity_badge.setAlignment(Qt.AlignCenter)
        self._severity_badge.setVisible(False)
        top_row.addWidget(self._severity_badge)
        layout.addLayout(top_row)

        metrics_row = QHBoxLayout()
        self._temp_label = QLabel("—")
        self._temp_label.setStyleSheet("font-size: 22px; font-weight: 650;")
        metrics_row.addWidget(self._temp_label)
        self._cond_label = QLabel("No station configured")
        self._cond_label.setStyleSheet("color: rgba(128,128,128,0.9); font-size: 11px;")
        metrics_row.addWidget(self._cond_label, 1)
        layout.addLayout(metrics_row)

        self._wind_label = QLabel("")
        self._wind_label.setStyleSheet("font-size: 10.5px; color: rgba(128,128,128,0.9);")
        layout.addWidget(self._wind_label)

        self._alert_label = QLabel("")
        self._alert_label.setStyleSheet("font-size: 10.5px; font-weight: 600;")
        layout.addWidget(self._alert_label)

        layout.addWidget(self._updated_label())

        subscribe_theme(self, self._on_theme_changed)
        self.refresh()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().mousePressEvent(event)
        window = self.window()
        opener = getattr(window, "open_weather_panel", None)
        if callable(opener):
            opener(initial_tab="forecast")

    def _ensure_manager(self):
        incident_id = get_active_incident_id()
        if not incident_id:
            self._manager = None
            self._incident_id = None
            return None
        if incident_id != self._incident_id:
            self._manager = get_weather_manager(incident_id)
            self._incident_id = incident_id
            self._manager.snapshotUpdated.connect(lambda *_: self.refresh())
            self._manager.alertsUpdated.connect(lambda *_: self.refresh())
        return self._manager

    def _on_theme_changed(self, _theme_name: str = "") -> None:
        self.refresh()

    def refresh(self) -> None:
        manager = self._ensure_manager()
        if manager is None:
            self._location_label.setText("Weather")
            self._cond_label.setText("No active incident")
            self._temp_label.setText("—")
            self._wind_label.setText("")
            self._severity_badge.setVisible(False)
            self._alert_label.setText("")
            self._touch_timestamp()
            return

        location = manager.default_location()
        if location is None:
            self._location_label.setText("Weather")
            self._cond_label.setText("No station configured")
            self._temp_label.setText("—")
            self._wind_label.setText("")
            self._severity_badge.setVisible(False)
            self._alert_label.setText("")
            self._touch_timestamp()
            return

        self._location_label.setText(location.label)
        reading = manager.normalized_current(location.location_id)
        temp_f = reading.get("temperature_f")
        self._temp_label.setText(f"{temp_f:.0f}°F" if isinstance(temp_f, (int, float)) else "—")

        snap = manager.snapshot(location.location_id)
        metar = snap.metar if snap else None
        condition_text = "Conditions unavailable"
        if metar is not None and metar.decoded:
            wx = metar.decoded.get("wxString")
            condition_text = str(wx) if wx else "Clear/VFR"
        self._cond_label.setText(condition_text)

        wind_kt = reading.get("wind_speed_kt")
        gust_kt = reading.get("wind_gust_kt")
        if isinstance(wind_kt, (int, float)):
            wind_text = f"Wind {wind_kt:.0f} kt"
            if isinstance(gust_kt, (int, float)) and gust_kt > wind_kt:
                wind_text += f", gust {gust_kt:.0f} kt"
            self._wind_label.setText(wind_text)
        else:
            self._wind_label.setText("")

        advisories = snap.advisories if snap else []
        severity_order = {"extreme": 4, "severe": 3, "moderate": 2, "minor": 1, "unknown": 0}
        colors = weather_severity_colors()
        if advisories:
            highest = max(advisories, key=lambda a: severity_order.get((a.severity or "unknown").lower(), 0))
            key = (highest.severity or "unknown").lower()
            palette = colors.get(key, colors.get("unknown"))
            self._apply_badge(key.title(), palette)
            count_text = "1 active alert" if len(advisories) == 1 else f"{len(advisories)} active alerts"
            self._alert_label.setText(count_text)
            self._alert_label.setStyleSheet(f"font-size: 10.5px; font-weight: 600; color: {palette['fg'].color().name()};")
        else:
            self._severity_badge.setVisible(False)
            self._alert_label.setText("")

        self._touch_timestamp()

    def _apply_badge(self, text: str, palette) -> None:
        self._severity_badge.setText(text)
        self._severity_badge.setVisible(True)
        bg = palette["bg"].color().name()
        fg = palette["fg"].color().name()
        self._severity_badge.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border-radius: 4px; "
            "padding: 2px 6px; font-size: 9.5px; font-weight: 700;"
        )


__all__ = ["WeatherDashboardTile"]
