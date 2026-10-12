"""Multi-series, toggleable trend chart for the History tab.

pyqtgraph was chosen over matplotlib/QtCharts: pure-Python, PySide6-native
painting (no separate native-widget embedding), lightweight dependency, and
easy to theme via our own style accessors rather than fighting a separate
rendering stack's default palette.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import pyqtgraph as pg
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QVBoxLayout, QWidget

from utils.styles import subscribe_theme

_SERIES_COLORS: Dict[str, str] = {
    "temperature_f": "#2f6fb0",
    "wind_gust_kt": "#c1440e",
    "relative_humidity_pct": "#1f7a52",
    "dew_point_f": "#8e6fdc",
    "barometric_pressure_hpa": "#3aa0a0",
    "visibility_sm": "#c98a3a",
}

_SERIES_LABELS: Dict[str, str] = {
    "temperature_f": "Temperature (°F)",
    "wind_gust_kt": "Wind gust (kt)",
    "relative_humidity_pct": "Humidity (%)",
    "dew_point_f": "Dew point (°F)",
    "barometric_pressure_hpa": "Pressure (hPa)",
    "visibility_sm": "Visibility (sm)",
}


class TrendChartWidget(QWidget):
    """Wraps a pg.PlotWidget; exposes set_series() per metric and checkboxes to toggle them."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._toggle_row = QHBoxLayout()
        layout.addLayout(self._toggle_row)

        self._plot = pg.PlotWidget()
        self._plot.showGrid(x=True, y=True, alpha=0.15)
        self._plot.addLegend()
        layout.addWidget(self._plot, 1)

        self._curves: Dict[str, pg.PlotDataItem] = {}
        self._checkboxes: Dict[str, QCheckBox] = {}
        self._series_data: Dict[str, tuple] = {}

        subscribe_theme(self, self._apply_theme)
        self._apply_theme()

    def _apply_theme(self, _theme_name: str = "") -> None:
        self._plot.setBackground(None)

    def set_series(
        self,
        metric: str,
        times: List[datetime],
        values: List[Optional[float]],
        *,
        visible: bool = True,
    ) -> None:
        """Set/replace one metric's data. Adds a toggle checkbox on first call."""
        xs = [t.timestamp() for t in times]
        ys = [v if v is not None else float("nan") for v in values]
        color = _SERIES_COLORS.get(metric, "#888888")
        label = _SERIES_LABELS.get(metric, metric)
        self._series_data[metric] = (xs, ys)

        if metric not in self._curves:
            checkbox = QCheckBox(label)
            checkbox.setChecked(visible)
            checkbox.toggled.connect(lambda checked, m=metric: self._set_visible(m, checked))
            self._toggle_row.addWidget(checkbox)
            self._checkboxes[metric] = checkbox
            pen = pg.mkPen(color=color, width=2)
            curve = self._plot.plot(xs, ys, pen=pen, name=label)
            curve.setVisible(visible)
            self._curves[metric] = curve
        else:
            self._curves[metric].setData(xs, ys)

    def _set_visible(self, metric: str, visible: bool) -> None:
        curve = self._curves.get(metric)
        if curve is not None:
            curve.setVisible(visible)

    def clear(self) -> None:
        for curve in self._curves.values():
            self._plot.removeItem(curve)
        self._curves.clear()
        self._series_data.clear()
        while self._toggle_row.count():
            item = self._toggle_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._checkboxes.clear()


__all__ = ["TrendChartWidget"]
