"""Form dialog used for creating or editing hospital catalog entries."""

from __future__ import annotations

from dataclasses import dataclass, replace
import sqlite3
from typing import Dict

from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator, QIntValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from models.hospital import Hospital
from services.hospital_service import HospitalService


@dataclass(frozen=True)
class _FieldSpec:
    name: str
    label: str
    kind: str  # "line", "int", "float", "bool", "combo", "text"
    placeholder: str = ""
    options: tuple[str, ...] = ()


_FIELD_SPECS = [
    _FieldSpec("name", "Name", "line", placeholder="Required"),
    _FieldSpec("code", "Code", "line"),
    _FieldSpec("type", "Type", "line"),
    _FieldSpec("contact_name", "Contact Name", "line"),
    _FieldSpec("contact", "Contact", "line"),
    _FieldSpec("phone", "Main Phone", "line"),
    _FieldSpec("phone_er", "ER Phone", "line"),
    _FieldSpec("phone_switchboard", "Switchboard", "line"),
    _FieldSpec("fax", "Fax", "line"),
    _FieldSpec("email", "Email", "line"),
    _FieldSpec("address", "Address", "line"),
    _FieldSpec("city", "City", "line"),
    _FieldSpec("state", "State / Province", "line"),
    _FieldSpec("zip", "Postal / ZIP", "line"),
    _FieldSpec("travel_time_min", "Travel Time (minutes)", "int"),
    _FieldSpec("helipad", "Helipad available", "bool"),
    _FieldSpec("trauma_level", "Trauma Level", "combo", options=("", "I", "II", "III", "IV")),
    _FieldSpec("burn_center", "Burn Center", "bool"),
    _FieldSpec("pediatric_capability", "Pediatric Capability", "bool"),
    _FieldSpec("bed_available", "Beds Available", "int"),
    _FieldSpec("diversion_status", "Diversion Status", "line"),
    _FieldSpec("ambulance_radio_channel", "Ambulance Radio Channel", "line"),
    _FieldSpec("lat", "Latitude", "float"),
    _FieldSpec("lon", "Longitude", "float"),
    _FieldSpec("notes", "Notes", "text"),
    _FieldSpec("is_active", "Active", "bool"),
]


class HospitalEditDialog(QDialog):
    """Dialog that edits a single :class:`Hospital` instance."""

    def __init__(
        self,
        service: HospitalService,
        hospital: Hospital | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._original = hospital
        self.hospital: Hospital | None = None
        self._available_columns = set(service.available_columns)
        self._field_widgets: Dict[str, QWidget] = {}
        self._field_specs: Dict[str, _FieldSpec] = {spec.name: spec for spec in _FIELD_SPECS}

        self.setWindowTitle("Edit Hospital" if hospital else "New Hospital")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        info = QLabel(
            "Enter the details for the hospital. Fields left blank will be stored as"
            " empty values."
        )
        info.setWordWrap(True)
        info.setObjectName("hospitalEditInfo")
        layout.addWidget(info)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)

        for spec in _FIELD_SPECS:
            if spec.name != "name" and spec.name not in self._available_columns:
                continue
            widget = self._create_widget(spec)
            self._field_widgets[spec.name] = widget
            if spec.kind == "bool":
                form.addRow("", widget)
            else:
                form.addRow(spec.label + ":", widget)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._populate_from_model()
        name_widget = self._field_widgets.get("name")
        if isinstance(name_widget, QLineEdit):
            name_widget.setFocus()

        self.resize(520, 640)

    # ----- UI helpers --------------------------------------------------
    def _create_widget(self, spec: _FieldSpec) -> QWidget:
        if spec.kind == "line":
            widget = QLineEdit()
            widget.setPlaceholderText(spec.placeholder)
            return widget
        if spec.kind == "int":
            widget = QLineEdit()
            widget.setPlaceholderText(spec.placeholder or "Leave blank if unknown")
            widget.setValidator(QIntValidator(parent=widget))
            return widget
        if spec.kind == "float":
            widget = QLineEdit()
            widget.setPlaceholderText(spec.placeholder or "Leave blank if unknown")
            validator = QDoubleValidator(parent=widget)
            validator.setNotation(QDoubleValidator.Notation.StandardNotation)
            if spec.name == "lat":
                validator.setBottom(-90.0)
                validator.setTop(90.0)
                validator.setDecimals(6)
            elif spec.name == "lon":
                validator.setBottom(-180.0)
                validator.setTop(180.0)
                validator.setDecimals(6)
            widget.setValidator(validator)
            return widget
        if spec.kind == "bool":
            checkbox = QCheckBox(spec.label)
            checkbox.setTristate(False)
            return checkbox
        if spec.kind == "combo":
            combo = QComboBox()
            combo.setEditable(False)
            combo.addItems(list(spec.options))
            return combo
        if spec.kind == "text":
            text = QPlainTextEdit()
            text.setPlaceholderText(spec.placeholder)
            text.setFixedHeight(120)
            return text
        return QLineEdit()

    def _populate_from_model(self) -> None:
        if not self._original:
            return
        for name, widget in self._field_widgets.items():
            value = getattr(self._original, name, None)
            if isinstance(widget, QLineEdit):
                widget.setText("" if value is None else str(value))
            elif isinstance(widget, QComboBox):
                text = "" if value is None else str(value)
                index = widget.findText(text)
                if index < 0:
                    widget.addItem(text)
                    index = widget.findText(text)
                widget.setCurrentIndex(index)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QPlainTextEdit):
                widget.setPlainText("" if value is None else str(value))

    # ----- Validation & persistence -----------------------------------
    def _collect_values(self) -> Hospital:
        hospital = replace(self._original) if self._original else Hospital()
        for name, widget in self._field_widgets.items():
            spec = self._field_specs[name]
            if isinstance(widget, QLineEdit):
                text = widget.text().strip()
                if spec.kind == "int":
                    if text:
                        try:
                            setattr(hospital, name, int(text))
                        except ValueError as exc:  # pragma: no cover - guarded by validator
                            raise ValueError(f"{spec.label} must be an integer") from exc
                    else:
                        setattr(hospital, name, None)
                elif spec.kind == "float":
                    if text:
                        try:
                            value = float(text)
                        except ValueError as exc:  # pragma: no cover - guarded by validator
                            raise ValueError(f"{spec.label} must be a number") from exc
                        if name == "lat" and not (-90.0 <= value <= 90.0):
                            raise ValueError("Latitude must be between -90 and 90 degrees")
                        if name == "lon" and not (-180.0 <= value <= 180.0):
                            raise ValueError("Longitude must be between -180 and 180 degrees")
                        setattr(hospital, name, value)
                    else:
                        setattr(hospital, name, None)
                else:
                    setattr(hospital, name, text)
            elif isinstance(widget, QComboBox):
                setattr(hospital, name, widget.currentText().strip())
            elif isinstance(widget, QCheckBox):
                setattr(hospital, name, widget.isChecked())
            elif isinstance(widget, QPlainTextEdit):
                setattr(hospital, name, widget.toPlainText().strip())
        return hospital

    def _on_save(self) -> None:
        try:
            hospital = self._collect_values()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid data", str(exc))
            return

        if not hospital.name.strip():
            QMessageBox.warning(self, "Missing information", "Hospital name is required.")
            name_widget = self._field_widgets.get("name")
            if isinstance(name_widget, QLineEdit):
                name_widget.setFocus()
            return

        try:
            if hospital.id:
                self._service.update_hospital(hospital)
            else:
                new_id = self._service.create_hospital(hospital)
                hospital.id = new_id
        except ValueError as exc:
            QMessageBox.warning(self, "Unable to save", str(exc))
            return
        except sqlite3.Error as exc:  # pragma: no cover - depends on runtime DB state
            QMessageBox.critical(self, "Database error", f"Unable to save hospital: {exc}")
            return

        self.hospital = hospital
        self.accept()


__all__ = ["HospitalEditDialog"]

