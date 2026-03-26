"""Current & Forecast weather window (card UI).

Shows current and short-term forecast for one or more locations using
simple, readable cards. Defaults to the ICP location (when available)
and supports adding/removing locations.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QGuiApplication, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from ..services.settings import weather_settings
from utils.incident_meta import get_icp_location
from utils.geocoding import geocode_address


class CurrentForecastWindow(QMainWindow):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("currentForecastWindow")
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowTitle("Current & Forecast")
        self.resize(980, 680)

        self._locations: List[dict] = []  # {label, lat, lon}
        self._cards: Dict[str, ForecastCard] = {}

        self._setup_ui()
        self._load_locations()
        if not self._locations:
            try:
                icp = get_icp_location()
                if icp:
                    self._locations.append({"label": icp.address, "lat": icp.latitude, "lon": icp.longitude})
            except Exception:
                pass
        self._render_cards()
        self._refresh_all()

    def _setup_ui(self) -> None:
        self.toolbar = QToolBar("Weather Toolbar", self)
        self.toolbar.setMovable(False)
        add_action = QAction("Add", self)
        add_action.triggered.connect(self._add_location)
        self.toolbar.addAction(add_action)
        add_icp = QAction("Add ICP", self)
        add_icp.triggered.connect(self._add_icp)
        self.toolbar.addAction(add_icp)
        remove_action = QAction("Remove", self)
        remove_action.triggered.connect(self._remove_location)
        self.toolbar.addAction(remove_action)
        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self._refresh_all)
        self.toolbar.addAction(refresh_action)
        self.addToolBar(self.toolbar)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.scroll = QScrollArea(central)
        self.scroll.setWidgetResizable(True)
        self.list_container = QWidget(self.scroll)
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(8)
        self.list_container.setLayout(self.list_layout)
        self.scroll.setWidget(self.list_container)
        layout.addWidget(self.scroll)
        layout.addStretch(1)
        self.setCentralWidget(central)
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

    def _load_locations(self) -> None:
        raw = weather_settings().value("current_forecast/locations", "[]")
        try:
            items = json.loads(raw) if isinstance(raw, str) else (raw or [])
        except Exception:
            items = []
        self._locations = [x for x in items if isinstance(x, dict) and "lat" in x and "lon" in x]

    def _save_locations(self) -> None:
        try:
            weather_settings().set_value("current_forecast/locations", json.dumps(self._locations))
        except Exception:
            pass

    def _add_location(self) -> None:
        text, ok = QInputDialog.getText(self, "Add Location", "Address or place")
        if not (ok and text):
            return
        result = geocode_address(text)
        if not result:
            QMessageBox.warning(self, "Add Location", "Could not find that address.")
            return
        self._locations.append({"label": result.address, "lat": result.latitude, "lon": result.longitude})
        self._save_locations()
        self._render_cards()
        self._refresh_all()

    def _add_icp(self) -> None:
        icp = get_icp_location()
        if not icp:
            QMessageBox.information(self, "ICP Location", "ICP location is not set.")
            return
        self._locations.append({"label": icp.address, "lat": icp.latitude, "lon": icp.longitude})
        self._save_locations()
        self._render_cards()
        self._refresh_all()

    def _remove_location(self) -> None:
        if not self._locations:
            self.status_bar.showMessage("No locations to remove", 3000)
            return
        labels = [loc.get("label") or f"{loc.get('lat')},{loc.get('lon')}" for loc in self._locations]
        value, ok = QInputDialog.getItem(self, "Remove Location", "Location", labels, 0, False)
        if not (ok and value):
            return
        idx = labels.index(value)
        self._locations.pop(idx)
        self._save_locations()
        self._render_cards()
        self._refresh_all()

    def _refresh_all(self) -> None:
        self.status_bar.showMessage("Refreshing…")
        for loc in self._locations:
            key = self._key(loc)
            card = self._cards.get(key)
            if not card:
                continue
            try:
                forecast = self._fetch_structured(loc["lat"], loc["lon"], loc.get("label", ""))
                card.update_from_forecast(forecast)
            except Exception as e:
                card.show_error(str(e))
        self.status_bar.showMessage("Refreshed", 2000)

    def _render_cards(self) -> None:
        # Ensure a card exists per location and remove any stale ones
        wanted = {self._key(loc): loc for loc in self._locations}
        # Remove stale
        for key in list(self._cards.keys()):
            if key not in wanted:
                widget = self._cards.pop(key)
                try:
                    self.list_layout.removeWidget(widget)
                except Exception:
                    pass
                widget.deleteLater()
        # Add missing
        for key, loc in wanted.items():
            if key not in self._cards:
                card = ForecastCard(key, loc.get("label", ""), self.list_container)
                self.list_layout.addWidget(card)
                self._cards[key] = card
                card.removeRequested.connect(lambda k=key: self._remove_by_key(k))

    @staticmethod
    def _key(loc: dict) -> str:
        return f"{float(loc['lat']):.4f},{float(loc['lon']):.4f}"

    def _fetch_structured(self, lat: float, lon: float, label: str) -> dict:
        import httpx

        ua = {
            "User-Agent": "IncidentManagementAssistant/1.0 (contact: admin@example.invalid)",
            "Accept": "application/geo+json, application/json;q=0.9",
        }
        with httpx.Client(headers=ua, timeout=httpx.Timeout(10.0)) as client:
            p = client.get(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}")
            p.raise_for_status()
            pdata = p.json()
            props = pdata.get("properties", {})
            forecast_url = props.get("forecast")
            # Fallback to hourly if daily missing
            if not forecast_url:
                forecast_url = props.get("forecastHourly")
            place = props.get("relativeLocation", {}).get("properties", {})
            place_name = f"{place.get('city','')}, {place.get('state','')}".strip(", ")
            fcast = []
            if forecast_url:
                r = client.get(forecast_url)
                r.raise_for_status()
                fdata = r.json()
                fcast = (fdata.get("properties") or {}).get("periods") or []
        return {
            "place": place_name or label,
            "current": (fcast[0] if fcast else None),
            "next": fcast[1:5] if fcast else [],
        }

    def _remove_by_key(self, key: str) -> None:
        # Find and remove from locations by key
        for i, loc in enumerate(list(self._locations)):
            if self._key(loc) == key:
                self._locations.pop(i)
                break
        self._save_locations()
        self._render_cards()
        self._refresh_all()


class ForecastCard(QWidget):
    from PySide6.QtCore import Signal  # type: ignore
    removeRequested = Signal(str)

    def __init__(self, key: str, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.key = key
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(6)

        # Header row
        h = QGridLayout()
        h.setHorizontalSpacing(8)
        h.setVerticalSpacing(0)
        self.title = QLabel(title or key, self)
        self.title.setStyleSheet("font-weight: bold; font-size: 14px;")
        btn = QPushButton("Remove", self)
        btn.setFlat(True)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.clicked.connect(lambda: self.removeRequested.emit(self.key))
        h.addWidget(self.title, 0, 0)
        h.addWidget(btn, 0, 1, alignment=Qt.AlignRight)
        v.addLayout(h)

        # Current line
        self.current = QLabel("Current: —", self)
        cur_font = QFont("Segoe UI")
        cur_font.setPointSize(11)
        self.current.setFont(cur_font)
        v.addWidget(self.current)

        # Next periods grid (2x2)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(4)
        self.periods: List[QLabel] = []
        for r in range(2):
            for c in range(2):
                lbl = QLabel("—", self)
                lbl.setWordWrap(True)
                self.periods.append(lbl)
                grid.addWidget(lbl, r, c)
        v.addLayout(grid)

        # separator
        sep = QFrame(self)
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        v.addWidget(sep)

    def update_from_forecast(self, data: dict) -> None:
        place = data.get("place") or self.key
        self.title.setText(place)
        cur = data.get("current") or {}
        nm = cur.get("name") or "Now"
        tp = cur.get("temperature")
        un = cur.get("temperatureUnit") or "F"
        wind = cur.get("windSpeed") or ""
        sf = cur.get("shortForecast") or ""
        bits = [str(nm)]
        if tp is not None:
            bits.append(f"{tp}°{un}")
        if wind:
            bits.append(str(wind))
        if sf:
            bits.append(sf)
        self.current.setText("Current: " + ", ".join(bits))

        nxt = data.get("next") or []
        for i in range(4):
            text = "—"
            if i < len(nxt):
                item = nxt[i]
                nm = item.get("name") or "—"
                tp = item.get("temperature")
                un = item.get("temperatureUnit") or "F"
                sf = item.get("shortForecast") or ""
                parts = [nm]
                if tp is not None:
                    parts.append(f"{tp}°{un}")
                if sf:
                    parts.append(sf)
                text = ", ".join(parts)
            self.periods[i].setText(text)

    def show_error(self, message: str) -> None:
        self.current.setText(f"Error: {message}")


__all__ = ["CurrentForecastWindow", "ForecastCard"]
