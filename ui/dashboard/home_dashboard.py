from __future__ import annotations

import json
from typing import List, Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QGridLayout, QFrame
)

from ui.widgets.base import snap_width
from ui.widgets import registry as W
from ui.widgets.components import QuickEntryWidget
from ui.actions.quick_entry_actions import dispatch as qe_dispatch, execute_cli as qe_cli
from utils.settingsmanager import SettingsManager


class HomeDashboard(QWidget):
    """A simple dashboard that arranges widgets on a 12-column grid.

    Persists per-user layout via SettingsManager key: user_layouts.home
    Layout entries: { widgetId, x, y, w, h }
    """

    def __init__(self, settings: SettingsManager | None = None, parent=None):
        super().__init__(parent)
        self._settings = settings or SettingsManager()

        outer = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        grid = QGridLayout(container)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        # Load or seed default layout
        layout = self._load_layout()
        if not layout:
            layout = self._default_layout()
            self._save_layout(layout)

        # Create components per registry
        for item in layout:
            wid = item.get("widgetId")
            spec = W.REGISTRY.get(wid)
            if not spec:
                continue

            # construct component
            comp: QWidget
            if wid == "quickEntry":
                comp = QuickEntryWidget(qe_dispatch, qe_cli)
            else:
                if callable(spec.component):
                    comp = spec.component()  # type: ignore
                else:
                    comp = spec.component()  # type: ignore

            # Wrap in a frame for visual separation
            frame = QFrame(self)
            frame.setFrameShape(QFrame.StyledPanel)
            v = QVBoxLayout(frame)
            v.setContentsMargins(6, 6, 6, 6)
            v.addWidget(comp)

            # 12-col grid placement
            x = int(item.get("x", 0))
            y = int(item.get("y", 0))
            w = snap_width(int(item.get("w", spec.default_size.w)))
            h = max(1, int(item.get("h", spec.default_size.h)))

            # Use row/column spans to approximate size
            grid.addWidget(frame, y, x, h, w)

    def _load_layout(self) -> List[Dict]:
        data = self._settings.get("user_layouts", {})
        if isinstance(data, dict):
            return data.get("home", [])
        return []

    def _save_layout(self, layout: List[Dict]):
        root = self._settings.get("user_layouts", {})
        if not isinstance(root, dict):
            root = {}
        root["home"] = layout
        self._settings.set("user_layouts", root)

    def _default_layout(self) -> List[Dict]:
        # Per spec: include Quick Entry and Clock Dual by default
        return [
            {"widgetId": "quickEntry", "x": 0, "y": 0, "w": 8, "h": 1},
            {"widgetId": "clockDual",  "x": 8, "y": 0, "w": 4, "h": 1},
            {"widgetId": "incidentinfo","x": 0, "y": 1, "w": 6, "h": 1},
            {"widgetId": "teamstatusboard","x": 6, "y": 1, "w": 6, "h": 1},
        ]

