"""ICP Location configuration window (temporary utility under Command)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from utils import incident_meta
from utils.geocoding import geocode_address


class IcpLocationWindow(QMainWindow):
    """Small window to set and persist the ICP location for the active incident."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("icpLocationWindow")
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowTitle("Set ICP Location")
        self.resize(560, 260)
        self._setup_ui()
        self._load_existing()

    def _setup_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)
        self.address_edit = QLineEdit(central)
        self.address_edit.setPlaceholderText("Enter address or place name")
        form.addRow("Address", self.address_edit)
        self.lat_label = QLabel("—", central)
        self.lon_label = QLabel("—", central)
        form.addRow("Latitude", self.lat_label)
        form.addRow("Longitude", self.lon_label)
        outer.addLayout(form)

        buttons = QHBoxLayout()
        self.validate_btn = QPushButton("Validate", central)
        self.validate_btn.clicked.connect(self._validate)
        buttons.addWidget(self.validate_btn)
        self.save_btn = QPushButton("Save", central)
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save)
        buttons.addWidget(self.save_btn)
        buttons.addStretch(1)
        outer.addLayout(buttons)

        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

    def _load_existing(self) -> None:
        loc = incident_meta.get_icp_location()
        if loc:
            self.address_edit.setText(loc.address)
            self.lat_label.setText(f"{loc.latitude:.6f}")
            self.lon_label.setText(f"{loc.longitude:.6f}")
            self.save_btn.setEnabled(True)

    def _validate(self) -> None:
        text = self.address_edit.text().strip()
        if not text:
            QMessageBox.information(self, "ICP Location", "Please enter an address.")
            return
        self.status_bar.showMessage("Validating address…")
        self.validate_btn.setEnabled(False)
        try:
            result = geocode_address(text)
        finally:
            self.validate_btn.setEnabled(True)
        if not result:
            QMessageBox.warning(self, "Validation Failed", "Could not validate or locate that address.")
            self.status_bar.clearMessage()
            self.save_btn.setEnabled(False)
            return
        self.address_edit.setText(result.address)
        self.lat_label.setText(f"{result.latitude:.6f}")
        self.lon_label.setText(f"{result.longitude:.6f}")
        self.status_bar.showMessage("Address validated.")
        self.save_btn.setEnabled(True)

    def _save(self) -> None:
        addr = self.address_edit.text().strip()
        try:
            lat = float(self.lat_label.text())
            lon = float(self.lon_label.text())
        except Exception:
            QMessageBox.warning(self, "ICP Location", "Validate the address before saving.")
            return
        try:
            incident_meta.set_icp_location(addr, lat, lon)
        except Exception as e:
            QMessageBox.critical(self, "ICP Location", f"Failed to save location:\n{e}")
            return
        self.status_bar.showMessage("ICP location saved.", 3000)


def show_window(parent: Optional[Widget] = None) -> IcpLocationWindow:  # type: ignore[name-defined]
    window = IcpLocationWindow(parent)
    window.show()
    window.raise_()
    return window


__all__ = ["IcpLocationWindow", "show_window"]
