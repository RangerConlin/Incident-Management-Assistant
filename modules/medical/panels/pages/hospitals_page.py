"""Receiving Hospitals page."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QMessageBox, QDialog, QFormLayout, QLineEdit, QSpinBox,
    QDialogButtonBox, QMenu, QLabel
)

from ...models.ics206_models import HospitalsModel


class HospitalDialog(QDialog):
    def __init__(self, parent=None, data: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Hospital")
        form = QFormLayout(self)
        self.hospital = QLineEdit()
        self.trauma = QLineEdit()
        self.beds = QSpinBox(); self.beds.setRange(0, 10000)
        self.phone = QLineEdit()
        form.addRow("Hospital", self.hospital)
        form.addRow("Trauma Center", self.trauma)
        form.addRow("Bed Cap", self.beds)
        form.addRow("Phone (ER)", self.phone)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addRow(btns)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        if data:
            self.hospital.setText(data.get("hospital", ""))
            self.trauma.setText(data.get("trauma_center", ""))
            self.beds.setValue(int(data.get("bed_cap", 0)))
            self.phone.setText(data.get("phone_er", ""))

    def get_data(self) -> dict:
        return {
            "hospital": self.hospital.text(),
            "trauma_center": self.trauma.text(),
            "bed_cap": self.beds.value(),
            "phone_er": self.phone.text(),
        }


class HospitalsPage(QWidget):
    def __init__(self, bridge, parent=None) -> None:
        super().__init__(parent)
        self.bridge = bridge
        layout = QVBoxLayout(self)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("+ Add")
        self.btn_edit = QPushButton("Edit")
        self.btn_del = QPushButton("Remove")
        self.btn_import = QPushButton("Import from Master")
        for b in (self.btn_add, self.btn_edit, self.btn_del, self.btn_import):
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.model = HospitalsModel(self.bridge)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        layout.addWidget(self.table, 1)

        # Footer details
        footer = QFormLayout()
        self.address = QLineEdit(); footer.addRow("Address", self.address)
        self.city = QLineEdit(); footer.addRow("City", self.city)
        self.state = QLineEdit(); footer.addRow("State", self.state)
        self.zip = QLineEdit(); footer.addRow("Zip", self.zip)
        self.lat = QLineEdit(); footer.addRow("Helipad Lat", self.lat)
        self.lon = QLineEdit(); footer.addRow("Helipad Lon", self.lon)
        self.btn_save = QPushButton("Save Details")
        footer.addRow(self.btn_save)
        layout.addLayout(footer)

        self.btn_add.clicked.connect(self.on_add)
        self.btn_edit.clicked.connect(self.on_edit)
        self.btn_del.clicked.connect(self.on_delete)
        self.btn_import.clicked.connect(self.on_import)
        self.btn_save.clicked.connect(self.on_save_details)
        self.table.selectionModel().currentChanged.connect(self.on_selection)

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_menu)

        self.current_id: int | None = None

    def reload(self) -> None:
        self.model.refresh()

    def current_row(self) -> dict | None:
        idx = self.table.currentIndex()
        return self.model.row(idx) if idx.isValid() else None

    def on_add(self) -> None:
        dlg = HospitalDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self.model.insertRow(dlg.get_data())

    def on_edit(self) -> None:
        row = self.current_row()
        if not row:
            return
        dlg = HospitalDialog(self, row)
        if dlg.exec() == QDialog.Accepted:
            self.model.updateRow(row["id"], dlg.get_data())

    def on_delete(self) -> None:
        row = self.current_row()
        if not row:
            return
        if QMessageBox.question(self, "Remove", "Delete selected hospital?") == QMessageBox.Yes:
            self.model.removeRow(row["id"])

    def on_import(self) -> None:
        self.bridge.import_hospitals_from_master([])
        self.reload()

    def on_selection(self, current, _previous) -> None:
        row = self.current_row()
        if row:
            self.current_id = row["id"]
            self.address.setText(row.get("address", ""))
            self.city.setText(row.get("city", ""))
            self.state.setText(row.get("state", ""))
            self.zip.setText(row.get("zip", ""))
            self.lat.setText(str(row.get("helipad_lat", "")))
            self.lon.setText(str(row.get("helipad_lon", "")))
        else:
            self.current_id = None
            for w in (self.address, self.city, self.state, self.zip, self.lat, self.lon):
                w.clear()

    def on_save_details(self) -> None:
        if self.current_id is None:
            return
        details = {
            "address": self.address.text(),
            "city": self.city.text(),
            "state": self.state.text(),
            "zip": self.zip.text(),
            "helipad_lat": float(self.lat.text() or 0),
            "helipad_lon": float(self.lon.text() or 0),
        }
        self.bridge.update_hospital_details(self.current_id, details)
        self.model.refresh()

    def open_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.addAction("Edit", self.on_edit)
        menu.addAction("Remove", self.on_delete)
        menu.exec(self.table.viewport().mapToGlobal(pos))
