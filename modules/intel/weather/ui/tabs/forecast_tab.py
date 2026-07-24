"""Current & Forecast tab — current conditions card + forecast table.

Plain language throughout (no METAR abbreviations), standard units
(mph/°F) — aviation-specific detail lives in the Aviation tab instead.
"""

from __future__ import annotations

import re
from typing import Optional

from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...models.location import WeatherLocation
from ...services import thresholds as thresholds_service
from ...services.weather_manager import WeatherManager
from ..widgets.severity_badge import SeverityBadge


def _kt_to_mph(value: Optional[float]) -> Optional[float]:
    return value * 1.15078 if isinstance(value, (int, float)) else None


def _parse_leading_number(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    return float(match.group(1)) if match else None


class ForecastTab(QWidget):
    def __init__(self, manager: WeatherManager, parent=None):
        super().__init__(parent)
        self._manager = manager
        self._location: Optional[WeatherLocation] = None

        layout = QVBoxLayout(self)

        thresh_row = QHBoxLayout()
        self._wind_tile = self._make_tile("Wind gusts")
        self._vis_tile = self._make_tile("Visibility")
        self._ceiling_tile = self._make_tile("Cloud ceiling")
        self._heat_tile = self._make_tile("Feels like")
        for tile in (self._wind_tile, self._vis_tile, self._ceiling_tile, self._heat_tile):
            thresh_row.addWidget(tile["box"])
        layout.addLayout(thresh_row)

        current_box = QGroupBox("Current conditions")
        current_form = QVBoxLayout(current_box)
        self._current_rows: dict[str, QLabel] = {}
        for key, label in (
            ("temperature", "Temperature"),
            ("feels_like", "Feels like"),
            ("wind", "Wind"),
            ("visibility", "Visibility"),
            ("sky", "Sky condition"),
            ("humidity", "Humidity"),
            ("pressure", "Barometric pressure"),
        ):
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{label}:"))
            value_label = QLabel("—")
            row.addWidget(value_label, 1)
            current_form.addLayout(row)
            self._current_rows[key] = value_label
        layout.addWidget(current_box)

        layout.addWidget(QLabel("Forecast"))
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["Period", "Conditions", "Temp °F", "Chance of rain %", "Wind", "Gusts mph", "Air ops"]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table, 1)

        self._source_note = QLabel("")
        self._source_note.setWordWrap(True)
        self._source_note.setStyleSheet("color: rgba(128,128,128,0.9); font-size: 10.5px;")
        layout.addWidget(self._source_note)

        manager.snapshotUpdated.connect(self._on_snapshot)

    @staticmethod
    def _make_tile(label: str) -> dict:
        box = QGroupBox()
        layout = QVBoxLayout(box)
        title = QLabel(label)
        title.setStyleSheet("font-size: 9.5px; font-weight: 700; color: rgba(128,128,128,0.9);")
        value = QLabel("—")
        value.setStyleSheet("font-size: 16px; font-weight: 700;")
        limit = QLabel("")
        limit.setStyleSheet("font-size: 9.5px; color: rgba(128,128,128,0.9);")
        layout.addWidget(title)
        layout.addWidget(value)
        layout.addWidget(limit)
        return {"box": box, "value": value, "limit": limit}

    def set_location(self, location: Optional[WeatherLocation]) -> None:
        self._location = location
        self._render()

    def _on_snapshot(self, location_id: str, _snap) -> None:
        if self._location and location_id == self._location.location_id:
            self._render()

    def _render(self) -> None:
        if self._location is None:
            return
        reading = self._manager.normalized_current(self._location.location_id)
        snap = self._manager.snapshot(self._location.location_id)
        t = self._manager.thresholds().get("ground", {})

        wind_gust_mph = _kt_to_mph(reading.get("wind_gust_kt"))
        visibility_mi = reading.get("visibility_sm")  # sm ~= statute miles, same unit for our purposes
        ceiling_ft = reading.get("ceiling_ft")
        heat_index_f = self._estimate_heat_index(reading)

        self._set_tile(self._wind_tile, wind_gust_mph, "mph", t.get("wind_gust_marginal_mph"), t.get("wind_gust_nogo_mph"))
        self._set_tile(
            self._vis_tile, visibility_mi, "mi", t.get("visibility_marginal_mi"), t.get("visibility_nogo_mi"), lower_is_worse=True
        )
        self._set_tile(
            self._ceiling_tile, ceiling_ft, "ft", t.get("ceiling_marginal_ft"), t.get("ceiling_nogo_ft"), lower_is_worse=True
        )
        self._set_tile(self._heat_tile, heat_index_f, "°F", t.get("heat_index_marginal_f"), t.get("heat_index_nogo_f"))

        temp_f = reading.get("temperature_f")
        self._current_rows["temperature"].setText(f"{temp_f:.0f}°F" if temp_f is not None else "—")
        self._current_rows["feels_like"].setText(f"{heat_index_f:.0f}°F" if heat_index_f is not None else "—")
        wind_kt = reading.get("wind_speed_kt")
        wind_text = "—"
        if isinstance(wind_kt, (int, float)):
            wind_mph = _kt_to_mph(wind_kt)
            wind_text = f"{wind_mph:.0f} mph"
            if wind_gust_mph and wind_gust_mph > wind_mph:
                wind_text += f", gusting to {wind_gust_mph:.0f} mph"
        self._current_rows["wind"].setText(wind_text)
        self._current_rows["visibility"].setText(f"{visibility_mi:.0f} miles" if visibility_mi is not None else "—")
        self._current_rows["sky"].setText(f"Ceiling {ceiling_ft:.0f} ft" if ceiling_ft is not None else "Clear")
        rh = reading.get("relative_humidity_pct")
        self._current_rows["humidity"].setText(f"{rh:.0f}%" if rh is not None else "—")
        pressure = reading.get("barometric_pressure_hpa")
        self._current_rows["pressure"].setText(f"{pressure:.1f} hPa" if pressure is not None else "—")

        periods = snap.forecast if snap else []
        self._table.setRowCount(len(periods))
        for row, period in enumerate(periods):
            self._table.setItem(row, 0, QTableWidgetItem(period.name))
            self._table.setItem(row, 1, QTableWidgetItem(period.detailed_text or ""))
            self._table.setItem(
                row, 2, QTableWidgetItem(f"{period.temperature:.0f}" if period.temperature is not None else "—")
            )
            self._table.setItem(row, 3, QTableWidgetItem("—"))  # NWS point forecast doesn't include PoP in this model
            self._table.setItem(row, 4, QTableWidgetItem(period.wind_speed or "—"))
            gust_guess = _parse_leading_number(period.wind_speed)
            self._table.setItem(row, 5, QTableWidgetItem(f"{gust_guess:.0f}" if gust_guess is not None else "—"))
            verdict = "go"
            if gust_guess is not None:
                verdict = thresholds_service.evaluate_ground({"wind_gust_mph": gust_guess}, t)
            verdict_item = QTableWidgetItem(verdict.replace("_", "-").upper())
            self._table.setItem(row, 6, verdict_item)

        source_bits = ["Source: National Weather Service point forecast."]
        source_bits.append(
            "Air-ops Go/No-Go reflects only wind (NWS period forecasts don't include ceiling/visibility)."
        )
        self._source_note.setText(" ".join(source_bits))

    @staticmethod
    def _estimate_heat_index(reading: dict) -> Optional[float]:
        temp_f = reading.get("temperature_f")
        rh = reading.get("relative_humidity_pct")
        if not isinstance(temp_f, (int, float)) or not isinstance(rh, (int, float)) or temp_f < 80:
            return temp_f
        # NWS Rothfusz regression (valid roughly T>=80F, RH>=40%)
        hi = (
            -42.379
            + 2.04901523 * temp_f
            + 10.14333127 * rh
            - 0.22475541 * temp_f * rh
            - 0.00683783 * temp_f * temp_f
            - 0.05481717 * rh * rh
            + 0.00122874 * temp_f * temp_f * rh
            + 0.00085282 * temp_f * rh * rh
            - 0.00000199 * temp_f * temp_f * rh * rh
        )
        return hi

    @staticmethod
    def _set_tile(tile: dict, value, unit: str, marginal, nogo, *, lower_is_worse: bool = False) -> None:
        if value is None:
            tile["value"].setText("—")
            tile["limit"].setText("")
            return
        tile["value"].setText(f"{value:.0f} {unit}")
        if marginal is not None and nogo is not None:
            tile["limit"].setText(f"marginal {marginal:.0f} · no-go {nogo:.0f} {unit}")
            check = thresholds_service.MetricCheck("m", value, marginal, nogo, higher_is_worse=not lower_is_worse)
            verdict = check.verdict()
            color = {"go": "#1f7a52", "marginal": "#946b00", "no_go": "#a3123a"}[verdict]
            tile["value"].setStyleSheet(f"font-size: 16px; font-weight: 700; color: {color};")


__all__ = ["ForecastTab"]
