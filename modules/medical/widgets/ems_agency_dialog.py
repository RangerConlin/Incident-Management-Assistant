"""Add/Edit dialog for EMS agencies."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from styles import styles as app_styles
from styles import tokens

from ..data.ems_agencies_schema import EMS_AGENCY_TYPES, EMSAgencyRepository


@dataclass
class DialogResult:
    """Structured response from the dialog."""

    agency_id: int
    payload: Dict[str, Any]


class EMSAgencyDialog(QDialog):
    """Modal dialog used to create or edit EMS agency records."""

    def __init__(
        self,
        repository: EMSAgencyRepository,
        *,
        parent: QWidget | None = None,
        agency: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._repository = repository
        self._agency = dict(agency) if agency else None
        self._result: DialogResult | None = None
        self._build_ui()
        if self._agency:
            self._load_agency(self._agency)

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        title = "Edit EMS Agency" if self._agency else "New EMS Agency"
        self.setWindowTitle(title)
        pal = app_styles.get_palette()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(tokens.DEFAULT_PADDING, tokens.DEFAULT_PADDING, tokens.DEFAULT_PADDING, tokens.DEFAULT_PADDING)
        layout.setSpacing(tokens.SECTION_SPACING)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(tokens.DEFAULT_PADDING)
        form.setVerticalSpacing(tokens.SMALL_PADDING)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Required")
        form.addRow("Name*", self.name_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItems(EMS_AGENCY_TYPES)
        form.addRow("Type*", self.type_combo)

        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("Primary contact numbers")
        form.addRow("Phone", self.phone_edit)

        self.radio_edit = QLineEdit()
        form.addRow("Radio/Channel", self.radio_edit)

        self.address_edit = QLineEdit()
        form.addRow("Address", self.address_edit)

        city_state_zip = QWidget()
        city_layout = QHBoxLayout(city_state_zip)
        city_layout.setContentsMargins(0, 0, 0, 0)
        city_layout.setSpacing(tokens.SMALL_PADDING)
        self.city_edit = QLineEdit()
        self.city_edit.setPlaceholderText("City")
        self.state_edit = QLineEdit()
        self.state_edit.setPlaceholderText("State")
        self.state_edit.setMaxLength(2)
        self.zip_edit = QLineEdit()
        self.zip_edit.setPlaceholderText("ZIP")
        city_layout.addWidget(self.city_edit)
        city_layout.addWidget(self.state_edit)
        city_layout.addWidget(self.zip_edit)
        form.addRow("City / State / ZIP", city_state_zip)

        coords_widget = QWidget()
        coords_layout = QHBoxLayout(coords_widget)
        coords_layout.setContentsMargins(0, 0, 0, 0)
        coords_layout.setSpacing(tokens.SMALL_PADDING)
        self.lat_edit = QLineEdit()
        self.lat_edit.setPlaceholderText("Latitude")
        self.lon_edit = QLineEdit()
        self.lon_edit.setPlaceholderText("Longitude")
        coords_layout.addWidget(self.lat_edit)
        coords_layout.addWidget(self.lon_edit)
        form.addRow("Coordinates", coords_widget)

        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Notes / remarks")
        self.notes_edit.setMaximumHeight(120)
        form.addRow("Notes", self.notes_edit)

        flags_widget = QWidget()
        flags_layout = QHBoxLayout(flags_widget)
        flags_layout.setContentsMargins(0, 0, 0, 0)
        flags_layout.setSpacing(tokens.DEFAULT_PADDING)
        self.default_check = QCheckBox("Default on ICS-206")
        self.active_check = QCheckBox("Active")
        self.active_check.setChecked(True)
        flags_layout.addWidget(self.default_check)
        flags_layout.addWidget(self.active_check)
        flags_layout.addStretch(1)
        form.addRow("Flags", flags_widget)

        layout.addLayout(form)

        info = QLabel("Fields marked with * are required.")
        info.setStyleSheet(f"color: {pal['muted'].name()};")
        layout.addWidget(info)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setMinimumWidth(420)

    # ------------------------------------------------------------------
    def _load_agency(self, agency: Mapping[str, Any]) -> None:
        self.name_edit.setText(str(agency.get("name") or ""))
        type_value = str(agency.get("type") or "")
        index = self.type_combo.findText(type_value)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)
        self.phone_edit.setText(str(agency.get("phone") or ""))
        self.radio_edit.setText(str(agency.get("radio_channel") or ""))
        self.address_edit.setText(str(agency.get("address") or ""))
        self.city_edit.setText(str(agency.get("city") or ""))
        self.state_edit.setText(str(agency.get("state") or ""))
        self.zip_edit.setText(str(agency.get("zip") or ""))
        lat = agency.get("lat")
        lon = agency.get("lon")
        self.lat_edit.setText("" if lat in (None, "") else str(lat))
        self.lon_edit.setText("" if lon in (None, "") else str(lon))
        self.notes_edit.setPlainText(str(agency.get("notes") or ""))
        self.default_check.setChecked(bool(agency.get("default_on_206")))
        self.active_check.setChecked(bool(agency.get("is_active", True)))

    # ------------------------------------------------------------------
    def _collect_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "name": self.name_edit.text().strip(),
            "type": self.type_combo.currentText(),
            "phone": self.phone_edit.text().strip(),
            "radio_channel": self.radio_edit.text().strip(),
            "address": self.address_edit.text().strip(),
            "city": self.city_edit.text().strip(),
            "state": self.state_edit.text().strip(),
            "zip": self.zip_edit.text().strip(),
            "lat": self.lat_edit.text().strip(),
            "lon": self.lon_edit.text().strip(),
            "notes": self.notes_edit.toPlainText().strip(),
            "default_on_206": self.default_check.isChecked(),
            "is_active": self.active_check.isChecked(),
        }
        return payload

    # ------------------------------------------------------------------
    def accept(self) -> None:  # noqa: D401 - Qt signature
        payload = self._collect_payload()
        try:
            if self._agency:
                agency_id = int(self._agency.get("id"))
                self._repository.update(agency_id, payload)
                self._result = DialogResult(agency_id, payload)
            else:
                agency_id = self._repository.create(payload)
                self._result = DialogResult(agency_id, payload)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid data", str(exc))
            return
        except Exception as exc:  # pragma: no cover - runtime DB failures
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        super().accept()

    # ------------------------------------------------------------------
    def result_data(self) -> DialogResult | None:
        return self._result


__all__ = ["EMSAgencyDialog", "DialogResult"]
