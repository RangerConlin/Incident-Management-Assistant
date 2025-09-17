"""Vehicle inventory editing dialog implemented with Qt widgets."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional, Protocol

import httpx
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

DEFAULT_API_BASE_URL = os.environ.get("IMA_API_BASE_URL", "http://localhost:8000")


class ApiClient(Protocol):
    """Protocol describing the minimal JSON HTTP client interface."""

    def get(self, path: str) -> Any:
        """Return JSON payload for a GET request."""

    def post(self, path: str, json: dict[str, Any]) -> Any:
        """Return JSON payload for a POST request."""

    def put(self, path: str, json: dict[str, Any]) -> Any:
        """Return JSON payload for a PUT request."""


class HttpApiClient:
    """Simple HTTP client powered by httpx for JSON APIs."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 10.0) -> None:
        self._base_url = (base_url or DEFAULT_API_BASE_URL).rstrip("/")
        self._timeout = timeout

    def _make_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self._base_url}{path}"

    def get(self, path: str) -> Any:
        response = httpx.get(self._make_url(path), timeout=self._timeout)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, json: dict[str, Any]) -> Any:
        response = httpx.post(self._make_url(path), json=json, timeout=self._timeout)
        response.raise_for_status()
        return response.json()

    def put(self, path: str, json: dict[str, Any]) -> Any:
        response = httpx.put(self._make_url(path), json=json, timeout=self._timeout)
        response.raise_for_status()
        return response.json()


class VehicleEditDialog(QDialog):
    """Modal dialog used to add or edit a single vehicle record."""

    vehicleSaved = Signal(dict)

    def __init__(
        self,
        vehicle_id: int | None = None,
        api_client: Optional[ApiClient] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._api_client: ApiClient = api_client or HttpApiClient()
        self._vehicle_id: int | None = None
        self._current_record: dict[str, Any] | None = None
        self._vehicle_types: list[dict[str, Any]] = []
        self._statuses: list[dict[str, Any]] = []
        self._references_loaded = False
        self._pending_vehicle_load = False

        self.id_value_label: QLabel
        self.license_plate_edit: QLineEdit
        self.vin_edit: QLineEdit
        self.year_edit: QLineEdit
        self.make_edit: QLineEdit
        self.model_edit: QLineEdit
        self.capacity_spin: QSpinBox
        self.type_combo: QComboBox
        self.status_combo: QComboBox
        self.tags_edit: QLineEdit
        self.save_button: QPushButton
        self.cancel_button: QPushButton

        self.setup_ui()
        self.set_vehicle_id(vehicle_id)
        self.load_reference_lists()

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------
    def setup_ui(self) -> None:
        """Build widgets, configure layout, and establish defaults."""

        self.setWindowTitle("Vehicle Editor")
        self.setModal(True)
        self.setMinimumWidth(520)

        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        main_layout.addLayout(form_layout)

        id_caption = QLabel("ID:")
        self.id_value_label = QLabel("New")
        self.id_value_label.setAccessibleName("Vehicle identifier")
        form_layout.addRow(id_caption, self.id_value_label)

        self.license_plate_edit = QLineEdit()
        self.license_plate_edit.setAccessibleName("License plate")
        self.license_plate_edit.setPlaceholderText("Required")
        license_label = QLabel("License Plate:")
        license_label.setBuddy(self.license_plate_edit)
        form_layout.addRow(license_label, self.license_plate_edit)

        self.vin_edit = QLineEdit()
        self.vin_edit.setAccessibleName("Vehicle identification number")
        self.vin_edit.setPlaceholderText("Required")
        vin_label = QLabel("VIN:")
        vin_label.setBuddy(self.vin_edit)
        form_layout.addRow(vin_label, self.vin_edit)

        vehicle_fields = QWidget()
        vehicle_row = QHBoxLayout(vehicle_fields)
        vehicle_row.setContentsMargins(0, 0, 0, 0)
        vehicle_row.setSpacing(8)

        self.year_edit = QLineEdit()
        self.year_edit.setAccessibleName("Vehicle year")
        self.year_edit.setPlaceholderText("Year")
        self.year_edit.setValidator(QIntValidator(1900, 2100, self.year_edit))
        vehicle_row.addWidget(self.year_edit)

        self.make_edit = QLineEdit()
        self.make_edit.setAccessibleName("Vehicle make")
        self.make_edit.setPlaceholderText("Make")
        vehicle_row.addWidget(self.make_edit)

        self.model_edit = QLineEdit()
        self.model_edit.setAccessibleName("Vehicle model")
        self.model_edit.setPlaceholderText("Model")
        vehicle_row.addWidget(self.model_edit)

        vehicle_label = QLabel("Vehicle:")
        vehicle_label.setBuddy(self.year_edit)
        form_layout.addRow(vehicle_label, vehicle_fields)

        self.capacity_spin = QSpinBox()
        self.capacity_spin.setRange(0, 100)
        self.capacity_spin.setAccessibleName("Passenger capacity")
        capacity_label = QLabel("Capacity:")
        capacity_label.setBuddy(self.capacity_spin)
        form_layout.addRow(capacity_label, self.capacity_spin)

        self.type_combo = QComboBox()
        self.type_combo.setAccessibleName("Vehicle type")
        self._configure_combo(self.type_combo)
        type_label = QLabel("Type:")
        type_label.setBuddy(self.type_combo)
        form_layout.addRow(type_label, self.type_combo)

        self.status_combo = QComboBox()
        self.status_combo.setAccessibleName("Vehicle status")
        self._configure_combo(self.status_combo)
        status_label = QLabel("Status:")
        status_label.setBuddy(self.status_combo)
        form_layout.addRow(status_label, self.status_combo)

        self.tags_edit = QLineEdit()
        self.tags_edit.setAccessibleName("Vehicle tags")
        self.tags_edit.setPlaceholderText("tag1, tag2")
        tags_label = QLabel("Tags:")
        tags_label.setBuddy(self.tags_edit)
        form_layout.addRow(tags_label, self.tags_edit)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.save_button = QPushButton("Save")
        self.save_button.setDefault(True)
        self.save_button.setAutoDefault(True)
        self.save_button.setEnabled(False)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setAutoDefault(False)
        button_row.addWidget(self.save_button)
        button_row.addWidget(self.cancel_button)
        main_layout.addLayout(button_row)

        self.save_button.clicked.connect(self.on_save_clicked)
        self.cancel_button.clicked.connect(self.reject)

        self.setTabOrder(self.license_plate_edit, self.vin_edit)
        self.setTabOrder(self.vin_edit, self.year_edit)
        self.setTabOrder(self.year_edit, self.make_edit)
        self.setTabOrder(self.make_edit, self.model_edit)
        self.setTabOrder(self.model_edit, self.capacity_spin)
        self.setTabOrder(self.capacity_spin, self.type_combo)
        self.setTabOrder(self.type_combo, self.status_combo)
        self.setTabOrder(self.status_combo, self.tags_edit)
        self.setTabOrder(self.tags_edit, self.save_button)
        self.setTabOrder(self.save_button, self.cancel_button)

        self.adjustSize()

    def _configure_combo(self, combo: QComboBox) -> None:
        """Apply a disabled placeholder entry to a combo box."""

        combo.clear()
        combo.addItem("(Select…)", None)
        model = combo.model()
        index = model.index(0, 0)
        model.setData(index, 0, Qt.UserRole - 1)
        combo.setCurrentIndex(0)
        combo.setEnabled(False)

    # ------------------------------------------------------------------
    # Data loading and population
    # ------------------------------------------------------------------
    def load_reference_lists(self) -> None:
        """Retrieve vehicle types and status values from the API."""

        self._references_loaded = False
        self._update_save_button_state()

        while True:
            try:
                types_payload = self._api_client.get("/api/vehicle-types")
                statuses_payload = self._api_client.get("/api/statuses")
                if not isinstance(types_payload, list):
                    raise ValueError("Vehicle types response was not a list")
                if not isinstance(statuses_payload, list):
                    raise ValueError("Statuses response was not a list")
            except Exception as exc:  # pragma: no cover - UI branch
                logger.error("Failed to load vehicle reference data: %s", exc)
                choice = QMessageBox.warning(
                    self,
                    "Reference Data Unavailable",
                    "Unable to load vehicle reference data.\n\n" + str(exc),
                    QMessageBox.Retry | QMessageBox.Cancel,
                )
                if choice == QMessageBox.Retry:
                    continue
                self._vehicle_types = []
                self._statuses = []
                self.type_combo.setEnabled(False)
                self.status_combo.setEnabled(False)
                return
            else:
                break

        self._vehicle_types = types_payload
        self._statuses = statuses_payload
        self._populate_combo(self.type_combo, self._vehicle_types)
        self._populate_combo(self.status_combo, self._statuses)
        self.type_combo.setEnabled(True)
        self.status_combo.setEnabled(True)
        self._references_loaded = True
        self._update_save_button_state()

        if self._pending_vehicle_load and self._vehicle_id is not None:
            self._pending_vehicle_load = False
            self._load_vehicle(self._vehicle_id)

    def _populate_combo(self, combo: QComboBox, entries: list[dict[str, Any]]) -> None:
        """Populate a combo box with name/id pairs."""

        combo.clear()
        combo.addItem("(Select…)", None)
        model = combo.model()
        index = model.index(0, 0)
        model.setData(index, 0, Qt.UserRole - 1)
        for entry in entries:
            entry_id = entry.get("id")
            label = entry.get("name") or str(entry_id)
            combo.addItem(label, entry_id)
        combo.setCurrentIndex(0)

    def _load_vehicle(self, vehicle_id: int) -> None:
        """Fetch a vehicle record and populate the form."""

        try:
            record = self._api_client.get(f"/api/vehicles/{vehicle_id}")
            if not isinstance(record, dict):
                raise ValueError("Vehicle response was not an object")
        except Exception as exc:  # pragma: no cover - UI branch
            logger.error("Failed to load vehicle %s: %s", vehicle_id, exc)
            QMessageBox.critical(
                self,
                "Unable to Load Vehicle",
                f"Failed to load vehicle #{vehicle_id}.\n\n{exc}",
            )
            return

        self.populate_from_record(record)

    def populate_from_record(self, record: dict[str, Any]) -> None:
        """Fill the widgets using values from an API record."""

        self._current_record = record
        self._vehicle_id = record.get("id", self._vehicle_id)
        self.id_value_label.setText(
            "New" if self._vehicle_id is None else str(self._vehicle_id)
        )
        self._update_window_title()

        self.license_plate_edit.setText(record.get("license_plate", "") or "")
        self.vin_edit.setText(record.get("vin", "") or "")

        year_value = record.get("year")
        self.year_edit.setText(str(year_value) if year_value is not None else "")

        self.make_edit.setText(record.get("make", "") or "")
        self.model_edit.setText(record.get("model", "") or "")

        capacity_value = record.get("capacity")
        if isinstance(capacity_value, int) and 0 <= capacity_value <= 100:
            self.capacity_spin.setValue(capacity_value)
        else:
            self.capacity_spin.setValue(0)

        self._select_combo_value(self.type_combo, record.get("type_id"))
        self._select_combo_value(self.status_combo, record.get("status_id"))

        tags = record.get("tags")
        if isinstance(tags, list):
            tags_text = ", ".join(str(tag) for tag in tags)
        else:
            tags_text = tags or ""
        self.tags_edit.setText(tags_text)

    def _select_combo_value(self, combo: QComboBox, value: Any) -> None:
        if value is None:
            combo.setCurrentIndex(0)
            return
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    # ------------------------------------------------------------------
    # Form state helpers
    # ------------------------------------------------------------------
    def clear_form(self) -> None:
        """Reset all user-editable fields to their defaults."""

        self.license_plate_edit.clear()
        self.vin_edit.clear()
        self.year_edit.clear()
        self.make_edit.clear()
        self.model_edit.clear()
        self.capacity_spin.setValue(0)
        if self.type_combo.count():
            self.type_combo.setCurrentIndex(0)
        if self.status_combo.count():
            self.status_combo.setCurrentIndex(0)
        self.tags_edit.clear()
        self._current_record = None

    def set_vehicle_id(self, vehicle_id: int | None) -> None:
        """Change the active vehicle being edited."""

        self._vehicle_id = vehicle_id
        self._pending_vehicle_load = vehicle_id is not None

        if vehicle_id is None:
            self.id_value_label.setText("New")
            self.clear_form()
        else:
            self.id_value_label.setText(str(vehicle_id))
            if self._references_loaded:
                self._pending_vehicle_load = False
                self._load_vehicle(vehicle_id)

        self._update_window_title()

    def _update_window_title(self) -> None:
        if self._vehicle_id is None:
            self.setWindowTitle("Add Vehicle")
        else:
            self.setWindowTitle(f"Edit Vehicle #{self._vehicle_id}")

    def _update_save_button_state(self) -> None:
        self.save_button.setEnabled(self._references_loaded)

    # ------------------------------------------------------------------
    # Payload collection and validation
    # ------------------------------------------------------------------
    def collect_payload(self) -> dict[str, Any]:
        """Collect the current form values into an API payload."""

        license_plate = self.license_plate_edit.text().strip()
        vin = self.vin_edit.text().strip()

        year_text = self.year_edit.text().strip()
        year_value: int | None = None
        if year_text:
            try:
                year_value = int(year_text)
            except ValueError as exc:
                raise ValueError("Year must be a number.") from exc

        make_text = self.make_edit.text().strip()
        model_text = self.model_edit.text().strip()

        tags = [
            tag.strip()
            for tag in self.tags_edit.text().split(",")
            if tag.strip()
        ]

        payload = {
            "license_plate": license_plate,
            "vin": vin,
            "year": year_value,
            "make": make_text or None,
            "model": model_text or None,
            "capacity": self.capacity_spin.value(),
            "type_id": self.type_combo.currentData(),
            "status_id": self.status_combo.currentData(),
            "tags": tags,
        }
        return payload

    def validate_payload(self, payload: dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate required fields and data ranges before saving."""

        if not payload.get("license_plate"):
            return False, "License plate is required."
        if not payload.get("vin"):
            return False, "VIN is required."

        year_value = payload.get("year")
        if year_value is not None and not (1900 <= year_value <= 2100):
            return False, "Year must be between 1900 and 2100."

        if payload.get("type_id") is None:
            return False, "Please select a vehicle type."
        if payload.get("status_id") is None:
            return False, "Please select a vehicle status."

        return True, None

    # ------------------------------------------------------------------
    # Save handling
    # ------------------------------------------------------------------
    def on_save_clicked(self) -> None:
        """Validate and submit the current vehicle record."""

        if not self._references_loaded:
            QMessageBox.warning(
                self,
                "Reference Data Missing",
                "Reference lists have not loaded yet. Please retry after they finish loading.",
            )
            return

        try:
            payload = self.collect_payload()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Input", str(exc))
            return

        valid, message = self.validate_payload(payload)
        if not valid:
            QMessageBox.warning(self, "Validation Error", message or "Invalid vehicle data.")
            return

        try:
            if self._vehicle_id is None:
                response = self._api_client.post("/api/vehicles", json=payload)
            else:
                response = self._api_client.put(
                    f"/api/vehicles/{self._vehicle_id}",
                    json=payload,
                )
        except Exception as exc:  # pragma: no cover - UI branch
            logger.error("Failed to save vehicle %s: %s", self._vehicle_id, exc)
            QMessageBox.critical(
                self,
                "Save Failed",
                self._format_error_message(exc),
            )
            return

        if not isinstance(response, dict):
            response = {"result": response}
        self.vehicleSaved.emit(response)
        self.accept()

    def _format_error_message(self, exc: Exception) -> str:
        """Generate a user-friendly description of an API error."""

        response = getattr(exc, "response", None)
        if response is not None:
            try:
                data = response.json()
            except Exception:  # pragma: no cover - defensive
                data = None
            if isinstance(data, dict):
                detail = data.get("detail") or data.get("message")
                if detail:
                    return f"Unable to save the vehicle.\n\n{detail}"
            text = getattr(response, "text", "")
            if text:
                return f"Unable to save the vehicle.\n\n{text}"
        return f"Unable to save the vehicle.\n\n{exc}"
