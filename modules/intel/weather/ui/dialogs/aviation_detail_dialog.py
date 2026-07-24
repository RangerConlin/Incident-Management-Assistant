"""Aviation station detail modal — full METAR decode, remarks, all TAF periods,
and every published runway's crosswind/headwind component."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...models.location import WeatherLocation
from ...models.readings import MetarReading, TafReading
from ...services import crosswind as crosswind_service
from ...services.weather_manager import WeatherManager


def _decoded_metar_lines(metar: Optional[MetarReading]) -> List[str]:
    if metar is None or not metar.decoded:
        return ["No current METAR available."]
    d = metar.decoded
    lines = []
    if isinstance(d.get("temp"), (int, float)):
        lines.append(f"Temperature / Dewpoint: {d['temp']:.0f}°C / {d.get('dewp', '—')}°C")
    if isinstance(d.get("wdir"), (int, float)) and isinstance(d.get("wspd"), (int, float)):
        gust = f", gust {d['wgst']:.0f} kt" if isinstance(d.get("wgst"), (int, float)) else ""
        lines.append(f"Wind: {d['wdir']:.0f}° at {d['wspd']:.0f} kt{gust}")
    if d.get("visib") is not None:
        lines.append(f"Visibility: {d['visib']} sm")
    if isinstance(d.get("altim"), (int, float)):
        lines.append(f"Altimeter: {d['altim']:.1f} hPa")
    clouds = d.get("clouds") or []
    for layer in clouds:
        if isinstance(layer, dict):
            lines.append(f"Sky: {layer.get('cover', '?')} at {layer.get('base', '?')} ft")
    return lines or ["Decoded METAR fields unavailable."]


_REMARK_GLOSSARY = {
    "AO2": "Automated station with precipitation discriminator",
    "AO1": "Automated station without precipitation discriminator",
    "SLP": "Sea-level pressure",
    "LTG": "Lightning observed",
}


def _remarks_lines(metar: Optional[MetarReading]) -> List[str]:
    if metar is None or not metar.raw_text or "RMK" not in metar.raw_text:
        return ["No remarks section reported."]
    remark_text = metar.raw_text.split("RMK", 1)[1].strip()
    tokens = remark_text.split()
    lines = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        matched = False
        for code, meaning in _REMARK_GLOSSARY.items():
            if token.startswith(code):
                lines.append(f"{token} — {meaning}")
                matched = True
                break
        if not matched:
            lines.append(token)
        i += 1
    return lines or ["No remarks section reported."]


class AviationDetailDialog(QDialog):
    def __init__(self, manager: WeatherManager, location: WeatherLocation, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Aviation — {location.label}")
        self.setModal(True)
        self.resize(640, 700)

        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)

        snap = manager.snapshot(location.location_id)
        metar = snap.metar if snap else None
        taf = snap.taf if snap else None
        reading = manager.normalized_current(location.location_id)

        layout.addWidget(self._heading("Current METAR — fully decoded"))
        for line in _decoded_metar_lines(metar):
            layout.addWidget(QLabel(line))

        layout.addWidget(self._heading("Remarks (RMK)"))
        for line in _remarks_lines(metar):
            layout.addWidget(QLabel(line))

        layout.addWidget(self._heading("Raw text"))
        raw_box = QTextEdit()
        raw_box.setReadOnly(True)
        raw_box.setMaximumHeight(60)
        raw_box.setPlainText((metar.raw_text if metar else "") or "No METAR text available.")
        layout.addWidget(raw_box)

        layout.addWidget(self._heading("Runway crosswind"))
        results = crosswind_service.all_runway_crosswinds(
            location.runway_ends, reading.get("wind_direction_deg"), reading.get("wind_speed_kt")
        )
        if results:
            table = QTableWidget(len(results), 4)
            table.setHorizontalHeaderLabels(["Runway", "Heading", "Crosswind (kt)", "Headwind (kt)"])
            for row, result in enumerate(results):
                table.setItem(row, 0, QTableWidgetItem(result.runway.designator))
                table.setItem(row, 1, QTableWidgetItem(f"{result.runway.heading_true_deg:.0f}°"))
                table.setItem(row, 2, QTableWidgetItem(f"{result.crosswind_kt:.0f}"))
                table.setItem(row, 3, QTableWidgetItem(f"{result.headwind_kt:.0f}"))
            layout.addWidget(table)
        else:
            layout.addWidget(QLabel("No runway data available for this station."))

        layout.addWidget(self._heading("All published TAF periods"))
        for line in self._taf_lines(taf):
            layout.addWidget(QLabel(line))

        layout.addStretch(1)

    @staticmethod
    def _heading(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-weight: 700; font-size: 11px; margin-top: 10px;")
        return label

    @staticmethod
    def _taf_lines(taf: Optional[TafReading]) -> List[str]:
        if taf is None or not taf.raw_text:
            return ["No TAF available."]
        return [taf.raw_text]


__all__ = ["AviationDetailDialog"]
