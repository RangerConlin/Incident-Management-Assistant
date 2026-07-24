"""Stations tab — list + detail management.

Follows modules/ui_customization/panels/layout_manager_panel.py's
list/Add/Edit/Delete/Set-Default convention. Auto-populated stations
(source != "manual") are not editable/deletable here — the note points to
the source record instead.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...models.location import WeatherLocation
from ...services.weather_manager import WeatherManager
from ..dialogs.station_edit_dialog import StationEditDialog

_SOURCE_LABELS = {
    "manual": "Manual",
    "initial_response": "Auto · Initial Response",
    "facility": "Auto · Facility",
}


class StationsTab(QWidget):
    def __init__(self, manager: WeatherManager, parent=None):
        super().__init__(parent)
        self._manager = manager

        layout = QHBoxLayout(self)

        left = QVBoxLayout()
        self._list = QListWidget()
        self._list.itemSelectionChanged.connect(self._render_detail)
        left.addWidget(self._list)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("+ Add")
        self._add_btn.clicked.connect(self._add_station)
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.clicked.connect(self._delete_selected)
        self._default_btn = QPushButton("Set Default")
        self._default_btn.clicked.connect(self._set_default_selected)
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._delete_btn)
        btn_row.addWidget(self._default_btn)
        left.addLayout(btn_row)
        layout.addLayout(left, 1)

        right = QVBoxLayout()
        self._detail_labels: dict[str, QLabel] = {}
        for key in ("label", "source", "coords", "icao", "default"):
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{key.title()}:"))
            value = QLabel("—")
            row.addWidget(value, 1)
            right.addLayout(row)
            self._detail_labels[key] = value
        self._auto_note = QLabel("")
        self._auto_note.setWordWrap(True)
        self._auto_note.setStyleSheet("color: rgba(128,128,128,0.9); font-size: 10.5px;")
        right.addWidget(self._auto_note)
        right.addStretch(1)
        layout.addLayout(right, 1)

        manager.locationsChanged.connect(lambda _locs: self._rebuild())
        self._rebuild()

    def _rebuild(self) -> None:
        self._list.clear()
        for location in self._manager.locations():
            text = location.label
            if location.is_default:
                text += "  [Default]"
            item = QListWidgetItem(text)
            item.setData(1, location.location_id)
            self._list.addItem(item)
        self._render_detail()

    def _selected_location(self) -> Optional[WeatherLocation]:
        items = self._list.selectedItems()
        if not items:
            return None
        location_id = items[0].data(1)
        return next((loc for loc in self._manager.locations() if loc.location_id == location_id), None)

    def _render_detail(self) -> None:
        location = self._selected_location()
        editable = location is not None and location.source == "manual"
        self._delete_btn.setEnabled(editable)
        self._default_btn.setEnabled(location is not None)
        if location is None:
            for label in self._detail_labels.values():
                label.setText("—")
            self._auto_note.setText("")
            return
        self._detail_labels["label"].setText(location.label)
        self._detail_labels["source"].setText(_SOURCE_LABELS.get(location.source, location.source))
        coords = "—"
        if location.latitude is not None and location.longitude is not None:
            coords = f"{location.latitude:.4f}, {location.longitude:.4f}"
        self._detail_labels["coords"].setText(coords)
        self._detail_labels["icao"].setText(", ".join(location.icao_codes) or "—")
        self._detail_labels["default"].setText("Yes" if location.is_default else "No")
        if not editable:
            self._auto_note.setText(
                "This station is auto-populated from Initial Response or a facility record; "
                "edit the source record instead of deleting it here."
            )
        else:
            self._auto_note.setText("")

    def _add_station(self) -> None:
        dialog = StationEditDialog(self)
        if dialog.exec():
            values = dialog.values()
            self._manager.add_manual_location(**values)

    def _delete_selected(self) -> None:
        location = self._selected_location()
        if location is not None and location.source == "manual":
            self._manager.remove_location(location.location_id)

    def _set_default_selected(self) -> None:
        location = self._selected_location()
        if location is not None:
            self._manager.set_default_location(location.location_id)


__all__ = ["StationsTab"]
