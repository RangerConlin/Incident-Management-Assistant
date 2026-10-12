"""Add one or more aviation stations by ICAO identifier.

Comma-separated identifiers (e.g. "KDTW, KLAN, KORD") are each resolved via
AWC's airport endpoint (services/runway_api.py) for name and coordinates —
no manual lat/lon entry, since every result is a real, looked-up airport.
"""

from __future__ import annotations

from typing import Any, Dict, List

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from ...services import runway_api


class AddAirportsDialog(QDialog):
    """Collect ICAO identifiers and resolve each to an airport via AWC."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Airport(s)")
        self.setModal(True)

        self._input = QLineEdit()
        self._input.setPlaceholderText("e.g. KDTW, KLAN, KORD")

        form = QFormLayout()
        form.addRow("ICAO identifier(s)", self._input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._handle_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Enter one or more ICAO airport identifiers, separated by commas."))
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._airports: List[Dict[str, Any]] = []

    def _handle_accept(self) -> None:
        text = self._input.text().strip()
        codes = [c.strip().upper() for c in text.replace(";", ",").split(",")]
        codes = [c for c in codes if c]
        if not codes:
            QMessageBox.warning(self, "Add Airport(s)", "Enter at least one ICAO identifier.")
            return

        found: List[Dict[str, Any]] = []
        not_found: List[str] = []
        for code in codes:
            info = runway_api.fetch_airport(code)
            if info is None or info.get("latitude") is None or info.get("longitude") is None:
                not_found.append(code)
            else:
                found.append(info)

        if not found:
            QMessageBox.warning(
                self,
                "Add Airport(s)",
                f"Could not find any of: {', '.join(codes)}. Check the identifiers and try again.",
            )
            return

        if not_found:
            QMessageBox.warning(
                self,
                "Add Airport(s)",
                f"Could not find: {', '.join(not_found)}. Adding the rest.",
            )

        self._airports = found
        self.accept()

    def airports(self) -> List[Dict[str, Any]]:
        """Each entry: {icao, name, latitude, longitude, runway_ends}."""
        return self._airports


__all__ = ["AddAirportsDialog"]
