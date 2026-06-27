"""Aviation weather viewer window (compact list view)."""

from __future__ import annotations

from typing import List, Dict
import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QGuiApplication, QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QInputDialog, QMainWindow, QPushButton, QStatusBar, QTextEdit, QToolBar, QVBoxLayout, QWidget, QLabel

from ..services.api_link import WeatherApiManager
from ..services.settings import weather_settings


class StationPanel(QWidget):
    """Widget representing METAR/TAF for a single station in the list."""

    removeRequested = Signal(str)

    def __init__(self, station: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.station = station
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)
        header = QLabel(f"{station}", self)
        header.setObjectName("stationHeader")
        header.setStyleSheet("font-weight: bold; font-size: 12px;")
        header_row.addWidget(header)
        header_row.addStretch(1)
        self.expand_btn = QPushButton("Expand", self)
        self.expand_btn.setFlat(True)
        self.expand_btn.setFocusPolicy(Qt.NoFocus)
        self.expand_btn.clicked.connect(self._on_toggle_expand)
        header_row.addWidget(self.expand_btn)
        self.remove_btn = QPushButton("Remove", self)
        self.remove_btn.setAccessibleName(f"Remove {station}")
        self.remove_btn.setFlat(True)
        self.remove_btn.setFocusPolicy(Qt.NoFocus)
        self.remove_btn.clicked.connect(self._on_remove)
        header_row.addWidget(self.remove_btn)
        layout.addLayout(header_row)

        mono = QFont("Consolas")
        mono.setStyleHint(QFont.Monospace)
        mono.setFixedPitch(True)

        self.raw_label = QTextEdit(self)
        self.raw_label.setReadOnly(True)
        self.raw_label.setAccessibleName(f"{station} METAR Raw Text")
        self.raw_label.setFont(mono)
        self.raw_label.setLineWrapMode(QTextEdit.NoWrap)
        self.raw_label.setStyleSheet("QTextEdit { border: 0; background: transparent; }")
        layout.addWidget(self.raw_label)
        self.decoded_label = QTextEdit(self)
        self.decoded_label.setReadOnly(True)
        self.decoded_label.setAccessibleName(f"{station} TAF Raw Text")
        self.decoded_label.setFont(mono)
        self.decoded_label.setLineWrapMode(QTextEdit.NoWrap)
        self.decoded_label.setStyleSheet("QTextEdit { border: 0; background: transparent; }")
        layout.addWidget(self.decoded_label)

        sep = QFrame(self)
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setStyleSheet("margin-top: 2px; margin-bottom: 2px;")
        layout.addWidget(sep)

        self._compact = True
        self._apply_compact_heights()

    def _on_remove(self) -> None:
        self.removeRequested.emit(self.station)

    def _on_toggle_expand(self) -> None:
        self._compact = not self._compact
        self.expand_btn.setText("Expand" if self._compact else "Collapse")
        self._apply_compact_heights()

    def _apply_compact_heights(self) -> None:
        # Compute heights based on font metrics to keep rows tight
        fm = self.raw_label.fontMetrics()
        lh = fm.lineSpacing()
        if self._compact:
            self.raw_label.setFixedHeight(int(lh * 1.6) + 6)   # ~1 line
            self.decoded_label.setFixedHeight(int(lh * 3.6) + 6)  # ~3 lines
        else:
            self.raw_label.setMinimumHeight(int(lh * 2.0) + 6)
            self.raw_label.setMaximumHeight(16777215)
            self.decoded_label.setMinimumHeight(int(lh * 6.0) + 6)
            self.decoded_label.setMaximumHeight(16777215)

    def update_content(self, metar: dict | None, taf: dict | None) -> None:
        def _get_raw(obj: dict | None, keys: list[str]) -> str | None:
            if not obj:
                return None
            if isinstance(obj, dict):
                for k in keys:
                    v = obj.get(k)
                    if v:
                        return str(v)
            return None

        metar_text = _get_raw(metar, ["raw_text", "rawOb", "rawText", "raw"]) or "No METAR received yet."
        self.raw_label.setPlainText(metar_text)

        taf_text = _get_raw(taf, ["raw_text", "rawTAF", "rawText", "raw"]) or "No TAF received yet."
        self.decoded_label.setPlainText(taf_text)
        self._apply_compact_heights()


class AviationWeatherWindow(QMainWindow):
    """Displays METAR and TAF data for selected stations in a single list."""

    def __init__(self, stations: List[str] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("aviationWeatherWindow")
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowTitle("Aviation Weather")
        self._set_initial_size()
        self._logger = logging.getLogger(__name__)
        self.api = WeatherApiManager.instance()
        self.api.dataUpdated.connect(self._handle_data)
        self.api.fetchFailed.connect(lambda ctx, err: self.status_bar.showMessage(f"{ctx} failed: {err}"))
        self._stations = [s.upper() for s in (stations or [])]
        self._metars: Dict[str, str] = {}
        self._tafs: Dict[str, str] = {}
        self._setup_ui()
        self._load_state()
        # Publish whatever is currently cached so the UI paints placeholders
        try:
            self.api.refresh_all()
        except Exception:
            pass
        self._ensure_visible_geometry()
        for station in self._stations:
            self._ensure_station_panel(station)

    def _setup_ui(self) -> None:
        self.toolbar = QToolBar("Aviation Toolbar", self)
        self.toolbar.setMovable(False)
        add_action = QAction("Add", self)
        add_action.triggered.connect(self._prompt_add_station)
        self.toolbar.addAction(add_action)
        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self._refresh_all_now)
        self.toolbar.addAction(refresh_action)
        remove_action = QAction("Remove", self)
        remove_action.setStatusTip("Remove a station from the list")
        remove_action.triggered.connect(self._prompt_remove_station)
        self.toolbar.addAction(remove_action)
        self.addToolBar(self.toolbar)

        # Scrollable list container
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Single combined text view (compact)
        self.combined_text = QTextEdit(central)
        self.combined_text.setReadOnly(True)
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setFixedPitch(True)
        font.setPointSize(11)
        self.combined_text.setFont(font)
        self.combined_text.setLineWrapMode(QTextEdit.WidgetWidth)
        self.combined_text.setStyleSheet("QTextEdit { border: 0; background: transparent; }")
        layout.addWidget(self.combined_text)

        self.setCentralWidget(central)
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        QWidget.setTabOrder(self.combined_text, self.status_bar)
        # trailing stretch keeps content compact at top
        layout.addStretch(1)

    def _set_initial_size(self) -> None:
        screen = self.screen() or QGuiApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None
        if avail:
            w = max(900, min(1200, int(avail.width() * 0.75)))
            h = max(600, min(800, int(avail.height() * 0.75)))
            self.resize(w, h)
        else:
            self.resize(1100, 720)

    def _prompt_add_station(self) -> None:
        station, ok = QInputDialog.getText(self, "Add Station", "ICAO")
        if ok and station:
            self._ensure_station_panel(station.upper())

    def _prompt_remove_station(self) -> None:
        if not self._stations:
            self.status_bar.showMessage("No stations to remove")
            return
        from PySide6.QtWidgets import QInputDialog
        station, ok = QInputDialog.getItem(
            self,
            "Remove Station",
            "Select ICAO",
            self._stations,
            0,
            False,
        )
        if ok and station:
            self._remove_station(station)

    def _ensure_station_panel(self, station: str) -> None:
        key = station.strip().upper()
        if not key:
            return
        if key in self._stations:
            return
        # Track but do not create per-station panels; render into a single view
        self._stations.append(key)
        self.api.add_station_code(key)
        self.api.request_metar([key])
        self.api.request_taf([key])
        if hasattr(self, "status_bar") and self.status_bar:
            self.status_bar.showMessage(f"Requested METAR/TAF for {key}")
        self._render_combined()

    def _remove_station(self, station: str) -> None:
        key = (station or "").strip().upper()
        self._metars.pop(key, None)
        self._tafs.pop(key, None)
        if key in self._stations:
            self._stations.remove(key)
            self.api.remove_station_code(key)
        if hasattr(self, "status_bar") and self.status_bar:
            self.status_bar.showMessage(f"Removed {key}")
        self._render_combined()

    def _handle_data(self, payload: dict) -> None:
        metar_entries = payload.get("metar", {}) or {}
        taf_entries = payload.get("taf", {}) or {}
        updated = 0
        for key in list(self._stations):
            metar = metar_entries.get(key)
            taf = taf_entries.get(key)
            if metar and isinstance(metar, dict):
                txt = metar.get("raw_text") or metar.get("rawOb") or metar.get("raw") or ""
                if txt:
                    self._metars[key] = str(txt)
                    updated += 1
            if taf and isinstance(taf, dict):
                txt = taf.get("raw_text") or taf.get("rawTAF") or taf.get("raw") or ""
                if txt:
                    self._tafs[key] = str(txt)
                    updated += 1
        self._render_combined()
        if hasattr(self, "status_bar") and self.status_bar:
            self.status_bar.showMessage(
                f"Updated {updated} station(s) | METAR keys: {', '.join(sorted(metar_entries.keys()))}"
            )
        # no extra debug UI in compact mode

    def _refresh_all_now(self) -> None:
        if hasattr(self, "status_bar") and self.status_bar:
            self.status_bar.showMessage("Refreshing stations…")
        if self._stations:
            self.api.request_metar(self._stations)
            self.api.request_taf(self._stations)
        try:
            self.api.refresh_all()
        except Exception:
            pass

    def _render_combined(self) -> None:
        lines: List[str] = []
        sep = "\n" + ("-" * 48) + "\n"
        for key in self._stations:
            lines.append(key)
            mt = self._metars.get(key) or "No METAR received yet."
            tf = self._tafs.get(key) or "No TAF received yet."
            lines.append(f"METAR: {mt}")
            lines.append(f"TAF:   {tf}")
            lines.append(sep)
        self.combined_text.setPlainText("\n".join(lines) if lines else "Add a station to begin.")

    def _load_state(self) -> None:
        geometry = weather_settings().value("geom/AviationWeatherWindow")
        if geometry:
            self.restoreGeometry(geometry)

    def _ensure_visible_geometry(self) -> None:
        screen = self.screen() or QGuiApplication.primaryScreen()
        if not screen:
            return
        avail = screen.availableGeometry()
        # Clamp size to 90% of available area if oversized
        new_w = min(self.width(), int(avail.width() * 0.9))
        new_h = min(self.height(), int(avail.height() * 0.9))
        if new_w != self.width() or new_h != self.height():
            self.resize(new_w, new_h)
        # If outside visible area, center it
        frame = self.frameGeometry()
        if not avail.contains(frame):
            x = avail.center().x() - self.width() // 2
            y = avail.center().y() - self.height() // 2
            self.move(max(avail.left(), x), max(avail.top(), y))

    def closeEvent(self, event) -> None:  # noqa: D401
        weather_settings().set_value("geom/AviationWeatherWindow", self.saveGeometry())
        super().closeEvent(event)


def show_window(stations: List[str] | None = None) -> AviationWeatherWindow:
    window = AviationWeatherWindow(stations or [])
    window.show()
    window.raise_()
    return window


__all__ = ["AviationWeatherWindow", "show_window"]
