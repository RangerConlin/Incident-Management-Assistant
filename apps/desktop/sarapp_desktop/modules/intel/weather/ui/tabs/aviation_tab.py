"""Aviation tab — one card per aviation-relevant station, click for full decode."""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...models.location import WeatherLocation
from ...services import crosswind as crosswind_service
from ...services import thresholds as thresholds_service
from ...services.weather_manager import WeatherManager
from ..dialogs.add_airports_dialog import AddAirportsDialog
from ..dialogs.aviation_detail_dialog import AviationDetailDialog
from ..widgets.severity_badge import SeverityBadge


class _AviationCard(QFrame):
    def __init__(self, manager: WeatherManager, location: WeatherLocation, parent=None):
        super().__init__(parent)
        self._manager = manager
        self._location = location
        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        top = QVBoxLayout()
        icao = location.icao_codes[0] if location.icao_codes else "—"
        self._id_label = QLabel(f"{icao}  {location.label}")
        self._id_label.setStyleSheet("font-weight: 700;")
        top.addWidget(self._id_label)
        layout.addLayout(top)

        self._badge = SeverityBadge("GO", "go")
        layout.addWidget(self._badge)

        self._metar_label = QLabel("")
        self._metar_label.setWordWrap(True)
        layout.addWidget(self._metar_label)

        self._xwind_label = QLabel("")
        layout.addWidget(self._xwind_label)

        self._taf_label = QLabel("")
        self._taf_label.setWordWrap(True)
        layout.addWidget(self._taf_label)

        self._hint = QLabel("Click for full decode →")
        self._hint.setStyleSheet("color: #2f6fb0; font-size: 10px;")
        layout.addWidget(self._hint)

        self.refresh()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        super().mousePressEvent(event)
        dialog = AviationDetailDialog(self._manager, self._location, self)
        dialog.exec()

    def refresh(self) -> None:
        reading = self._manager.normalized_current(self._location.location_id)
        snap = self._manager.snapshot(self._location.location_id)
        metar = snap.metar if snap else None
        taf = snap.taf if snap else None

        if metar is not None and metar.decoded:
            d = metar.decoded
            wind = f"{d.get('wdir', '—')}° at {d.get('wspd', '—')} kt"
            if isinstance(d.get("wgst"), (int, float)):
                wind += f", gust {d['wgst']:.0f} kt"
            vis = d.get("visib", "—")
            self._metar_label.setText(f"Wind {wind} · Visibility {vis} sm")
        else:
            self._metar_label.setText("No current METAR")

        best = crosswind_service.best_runway_crosswind(
            self._location.runway_ends, reading.get("wind_direction_deg"), reading.get("wind_speed_kt")
        )
        aviation_thresholds = self._manager.thresholds().get("aviation", {})
        if best is not None:
            self._xwind_label.setText(
                f"Best runway {best.runway.designator} · Crosswind {best.crosswind_kt:.0f} kt"
            )
            verdict = thresholds_service.evaluate_aviation(
                reading, aviation_thresholds, crosswind_kt=best.crosswind_kt
            )
        else:
            self._xwind_label.setText("Crosswind: no runway data available")
            verdict = thresholds_service.evaluate_aviation(reading, aviation_thresholds)

        self._badge.set_key(verdict, verdict.replace("_", "-"))

        if taf is not None and taf.raw_text:
            self._taf_label.setText(f"Next TAF: {taf.raw_text[:80]}")
        else:
            self._taf_label.setText("No TAF available")


class AviationTab(QWidget):
    def __init__(self, manager: WeatherManager, parent=None):
        super().__init__(parent)
        self._manager = manager
        self._cards: dict[str, _AviationCard] = {}

        outer = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        toolbar.addStretch(1)
        self._add_btn = QPushButton("+ Add")
        self._add_btn.setToolTip("Add airport(s) by ICAO identifier, e.g. KDTW, KLAN, KORD")
        self._add_btn.clicked.connect(self._add_airports)
        toolbar.addWidget(self._add_btn)
        outer.addLayout(toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        self._grid = QGridLayout(content)

        manager.snapshotUpdated.connect(self._on_snapshot)
        manager.locationsChanged.connect(lambda _locs: self._rebuild())
        self._rebuild()

    def _aviation_locations(self) -> List[WeatherLocation]:
        return [loc for loc in self._manager.locations() if loc.icao_codes]

    def _rebuild(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._cards.clear()

        locations = self._aviation_locations()
        if not locations:
            self._grid.addWidget(QLabel("No aviation-capable stations configured (add an ICAO code to a station)."), 0, 0)
            return
        for i, location in enumerate(locations):
            card = _AviationCard(self._manager, location)
            self._cards[location.location_id] = card
            self._grid.addWidget(card, i // 3, i % 3)

    def _on_snapshot(self, location_id: str, _snap) -> None:
        card = self._cards.get(location_id)
        if card is not None:
            card.refresh()

    def _add_airports(self) -> None:
        dialog = AddAirportsDialog(self)
        if not dialog.exec():
            return
        added = []
        for info in dialog.airports():
            self._manager.add_manual_location(
                label=f"{info['icao']} {info['name']}".strip(),
                latitude=info["latitude"],
                longitude=info["longitude"],
                icao_codes=[info["icao"]],
            )
            added.append(info["icao"])
        if added:
            QMessageBox.information(self, "Add Airport(s)", f"Added: {', '.join(added)}")


__all__ = ["AviationTab"]
