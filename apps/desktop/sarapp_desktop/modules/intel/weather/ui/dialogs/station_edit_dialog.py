"""Add a manual weather station/location.

Location is a single free-text field. The user can type either an address/
place name (geocoded automatically) or raw coordinates like "39.1031,
-84.512" (parsed directly) — useful for camps, helibases, or other spots
with no street address to look up. No separate lat/lon fields or "Geocode"
button exposed; the lookup/parsing is an implementation detail (see
utils/geocoding.py).
"""

from __future__ import annotations

import re
from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from utils.geocoding import geocode_address

_COORD_PATTERN = re.compile(
    r"^\s*([+-]?\d+(?:\.\d+)?)\s*[,\s]\s*([+-]?\d+(?:\.\d+)?)\s*$"
)


def _parse_coordinates(text: str) -> Optional[tuple[float, float]]:
    """Parse "lat, lon" / "lat lon" style input. Returns None if not coordinates."""
    match = _COORD_PATTERN.match(text)
    if not match:
        return None
    lat, lon = float(match.group(1)), float(match.group(2))
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return None
    return lat, lon


class StationEditDialog(QDialog):
    """Collect a manual station's label/location.

    ICAO codes (for aviation data) are added separately via the Aviation
    tab's "+ Add" button, which looks airports up by identifier instead of
    requiring the code to be typed correctly here.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Station")
        self.setModal(True)
        self.resize(480, self.sizeHint().height())

        self._label = QLineEdit()
        self._location = QLineEdit()
        self._location.setPlaceholderText("Address, place name, or coordinates (39.1031, -84.512)")
        self._is_default = QCheckBox("Set as default station")

        self._latitude: Optional[float] = None
        self._longitude: Optional[float] = None
        self._matched_address: Optional[str] = None

        form = QFormLayout()
        form.addRow("Label", self._label)
        form.addRow("Location", self._location)
        form.addRow(self._is_default)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._handle_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _handle_accept(self) -> None:
        text = self._location.text().strip()
        if not text:
            QMessageBox.warning(self, "Add Station", "Enter a location to look up.")
            return

        coords = _parse_coordinates(text)
        if coords is not None:
            self._latitude, self._longitude = coords
            self._matched_address = None
            self.accept()
            return

        result = geocode_address(text)
        if result is None:
            QMessageBox.warning(
                self,
                "Add Station",
                "Could not find that location. Check the spelling, or enter coordinates directly "
                "(e.g. 39.1031, -84.512) for spots with no address.",
            )
            return
        self._latitude = result.latitude
        self._longitude = result.longitude
        self._matched_address = result.address
        self.accept()

    def values(self) -> dict:
        return {
            "label": self._label.text().strip() or self._matched_address or "Unnamed station",
            "latitude": self._latitude,
            "longitude": self._longitude,
            "icao_codes": [],
            "is_default": self._is_default.isChecked(),
        }


__all__ = ["StationEditDialog"]
