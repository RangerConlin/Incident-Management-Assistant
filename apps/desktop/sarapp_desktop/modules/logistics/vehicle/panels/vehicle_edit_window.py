"""Vehicle inventory editing dialog implemented with Qt widgets.

No QML used.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

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

from modules.admin.resource_types.data import ApiResourceAssignmentRepository, ApiResourceTypeRepository
from modules.admin.resource_types.widgets import ResourceTypeSearchBox
from utils.org_combo import make_org_combo

logger = logging.getLogger(__name__)

_BASE = "/api/master/vehicles"

DEFAULT_STATUS_CHOICES: list[str] = [
    "Available",
    "In Service",
    "Out of Service",
    "Retired",
]

DEFAULT_TYPE_CHOICES: list[str] = [
    "Passenger Vehicle",
    "Utility",
    "Support",
    "Other",
]


def _client():
    from utils.api_client import api_client
    return api_client


def _id_sort_key(record: dict[str, Any]) -> tuple[int, Any]:
    """Sort vehicle ids numerically when possible, falling back to text.

    Vehicle ids may now be a legacy auto-assigned int or an arbitrary
    user-typed string, so a plain ``r.get("id")`` key raises ``TypeError``
    when the list mixes both types. The leading group flag keeps numeric
    and text ids from ever being compared against each other directly.
    """
    value = record.get("id")
    if value is None:
        return (1, "")
    if isinstance(value, int):
        return (0, value)
    text = str(value)
    if text.isdigit():
        return (0, int(text))
    return (1, text.lower())


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d["id"] = d.get("id") or d.get("vehicle_id")
    tags = d.get("tags")
    if isinstance(tags, str):
        d["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    elif tags is None:
        d["tags"] = []
    return d


class VehicleRepository:
    """API-backed repository for vehicle master catalog entries."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        self._db_path: Optional[Path] = Path(db_path) if db_path else None
        self._assignment_repo = ApiResourceAssignmentRepository()

    # ------------------------------------------------------------------
    # Reference data
    # ------------------------------------------------------------------
    def list_vehicles(self, search_text: str | None = None) -> list[dict[str, Any]]:
        try:
            params: dict[str, Any] = {}
            if search_text and search_text.strip():
                params["search"] = search_text.strip()
            docs = _client().get(_BASE, params=params or None) or []
            return [_normalize(d) for d in docs]
        except Exception:
            return []

    def list_vehicle_types(self) -> list[dict[str, Any]]:
        try:
            return _client().get(f"{_BASE}/types") or []
        except Exception:
            return [{"id": t, "name": t} for t in DEFAULT_TYPE_CHOICES]

    def list_statuses(self) -> list[dict[str, Any]]:
        try:
            return _client().get(f"{_BASE}/statuses") or []
        except Exception:
            return [{"id": s, "name": s} for s in DEFAULT_STATUS_CHOICES]

    # ------------------------------------------------------------------
    # CRUD helpers
    # ------------------------------------------------------------------
    def list_inventory(
        self,
        *,
        search: str | None = None,
        type_filter: Any | None = None,
        status_filter: Any | None = None,
        sort_key: str = "id",
        sort_order: str = "asc",
        offset: int = 0,
        limit: Optional[int] = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return vehicle records filtered, sorted, and paginated.

        Parameters mirror the vehicle inventory UI requirements. ``limit`` may
        be ``None`` to fetch all rows for background exports.
        """

        try:
            params: dict[str, Any] = {}
            if search:
                params["search"] = search.strip()
            if type_filter and type_filter != "All":
                params["type_filter"] = str(type_filter).strip()
            if status_filter and status_filter != "All":
                params["status_filter"] = str(status_filter).strip()
            docs = _client().get(_BASE, params=params or None) or []
            records = [_normalize(d) for d in docs]
        except Exception:
            return [], 0

        # Sort client-side
        reverse = str(sort_order).lower() == "desc"
        sort_map = {
            "license_plate": lambda r: (r.get("license_plate") or "").lower(),
            "vin": lambda r: (r.get("vin") or "").lower(),
            "vehicle": lambda r: " ".join(filter(None, [
                str(r.get("year") or ""), r.get("make") or "", r.get("model") or ""
            ])).lower(),
            "cap": lambda r: r.get("capacity") or 0,
            "capacity": lambda r: r.get("capacity") or 0,
            "type": lambda r: (r.get("type_id") or "").lower(),
            "status": lambda r: (r.get("status_id") or "").lower(),
            "id": _id_sort_key,
        }
        key_fn = sort_map.get(sort_key, _id_sort_key)
        records.sort(key=key_fn, reverse=reverse)

        total = len(records)
        if limit is not None:
            records = records[offset: offset + limit]
        return records, total

    def fetch_vehicle(self, vehicle_id: int | str) -> Optional[dict[str, Any]]:
        try:
            doc = _client().get(f"{_BASE}/{vehicle_id}")
            return _normalize(doc) if doc else None
        except Exception:
            return None

    def create_vehicle(self, payload: dict[str, Any]) -> dict[str, Any]:
        tags = payload.get("tags") or []
        if isinstance(tags, list):
            tags_str = ", ".join(str(t) for t in tags if t)
        else:
            tags_str = str(tags) if tags else ""
        body = {
            "id": payload.get("id") or None,
            "vin": payload.get("vin") or "",
            "license_plate": payload.get("license_plate") or "",
            "year": payload.get("year"),
            "make": payload.get("make") or "",
            "model": payload.get("model") or "",
            "capacity": payload.get("capacity") or 0,
            "type_id": payload.get("type_id") or "",
            "status_id": payload.get("status_id") or "Available",
            "tags": tags_str,
            "organization": payload.get("organization") or "",
            "resource_type_id": payload.get("resource_type_id"),
        }
        doc = _client().post(_BASE, json=body)
        return _normalize(doc)

    def update_vehicle(self, vehicle_id: int | str, payload: dict[str, Any]) -> dict[str, Any]:
        tags = payload.get("tags") or []
        if isinstance(tags, list):
            tags_str = ", ".join(str(t) for t in tags if t)
        else:
            tags_str = str(tags) if tags else ""
        body = {
            "id": payload.get("id") or None,
            "vin": payload.get("vin") or "",
            "license_plate": payload.get("license_plate") or "",
            "year": payload.get("year"),
            "make": payload.get("make") or "",
            "model": payload.get("model") or "",
            "capacity": payload.get("capacity") or 0,
            "type_id": payload.get("type_id") or "",
            "status_id": payload.get("status_id") or "Available",
            "tags": tags_str,
            "organization": payload.get("organization") or "",
            "resource_type_id": payload.get("resource_type_id"),
        }
        doc = _client().patch(f"{_BASE}/{vehicle_id}", json=body)
        if doc is None:
            raise LookupError(f"Vehicle {vehicle_id} does not exist")
        return _normalize(doc)


class VehicleEditDialog(QDialog):
    """Modal dialog used to add or edit a single vehicle record."""

    vehicleSaved = Signal(dict)

    def __init__(
        self,
        vehicle_id: int | str | None = None,
        repository: Optional[VehicleRepository] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._repository = repository or VehicleRepository()
        self._vehicle_id: int | str | None = None
        self._current_record: dict[str, Any] | None = None
        self._vehicle_types: list[dict[str, Any]] = []
        self._statuses: list[dict[str, Any]] = []
        self._references_loaded = False
        self._pending_vehicle_load = False

        self.id_edit: QLineEdit
        self.license_plate_edit: QLineEdit
        self.vin_edit: QLineEdit
        self.year_edit: QLineEdit
        self.make_edit: QLineEdit
        self.model_edit: QLineEdit
        self.capacity_spin: QSpinBox
        self.type_combo: QComboBox
        self.status_combo: QComboBox
        self.resource_type_search: ResourceTypeSearchBox
        self.org_combo: QComboBox
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

        id_caption = QLabel("Vehicle ID:")
        self.id_edit = QLineEdit()
        self.id_edit.setAccessibleName("Vehicle identifier / reference number")
        self.id_edit.setPlaceholderText("Auto-assigned if left blank")
        id_caption.setBuddy(self.id_edit)
        form_layout.addRow(id_caption, self.id_edit)

        self.license_plate_edit = QLineEdit()
        self.license_plate_edit.setAccessibleName("License plate")
        license_label = QLabel("License Plate:")
        license_label.setBuddy(self.license_plate_edit)
        form_layout.addRow(license_label, self.license_plate_edit)

        self.vin_edit = QLineEdit()
        self.vin_edit.setAccessibleName("Vehicle identification number")
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

        # Resource typing stays optional for backward compatibility. The smart
        # search box lets operators pick a library record when one exists.
        self.resource_type_search = ResourceTypeSearchBox(
            repository=ApiResourceTypeRepository(),
            parent=self,
        )
        self.resource_type_search.setAccessibleName("Vehicle resource type")
        form_layout.addRow(QLabel("Resource Type:"), self.resource_type_search)

        self.org_combo = make_org_combo()
        self.org_combo.setAccessibleName("Vehicle organization")
        org_label = QLabel("Organization:")
        org_label.setBuddy(self.org_combo)
        form_layout.addRow(org_label, self.org_combo)

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

        self.setTabOrder(self.id_edit, self.license_plate_edit)
        self.setTabOrder(self.license_plate_edit, self.vin_edit)
        self.setTabOrder(self.vin_edit, self.year_edit)
        self.setTabOrder(self.year_edit, self.make_edit)
        self.setTabOrder(self.make_edit, self.model_edit)
        self.setTabOrder(self.model_edit, self.capacity_spin)
        self.setTabOrder(self.capacity_spin, self.type_combo)
        self.setTabOrder(self.type_combo, self.status_combo)
        self.setTabOrder(self.status_combo, self.resource_type_search.line_edit)
        self.setTabOrder(self.resource_type_search.line_edit, self.org_combo)
        self.setTabOrder(self.org_combo, self.tags_edit)
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
        """Load vehicle types and statuses from the master database."""

        self._references_loaded = False
        self._update_save_button_state()

        while True:
            try:
                types_payload = self._repository.list_vehicle_types()
                statuses_payload = self._repository.list_statuses()
                if not types_payload or not statuses_payload:
                    raise ValueError("Reference lists are empty")
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

    def _load_vehicle(self, vehicle_id: int | str) -> None:
        """Fetch a vehicle record and populate the form."""

        try:
            record = self._repository.fetch_vehicle(vehicle_id)
            if record is None:
                raise LookupError(f"Vehicle {vehicle_id} was not found")
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
        """Fill the widgets using values from a stored vehicle record."""

        self._current_record = record
        self._vehicle_id = record.get("id", self._vehicle_id)
        self.id_edit.setText("" if self._vehicle_id is None else str(self._vehicle_id))
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
        self.resource_type_search.set_value(
            record.get("resource_type_id"),
            self._repository._assignment_repo.get_resource_type_name(record.get("resource_type_id")),
        )

        tags = record.get("tags")
        if isinstance(tags, list):
            tags_text = ", ".join(str(tag) for tag in tags)
        else:
            tags_text = tags or ""
        self.tags_edit.setText(tags_text)

        self.org_combo.setCurrentText(record.get("organization") or "")

    def _select_combo_value(self, combo: QComboBox, value: Any) -> None:
        if value is None:
            combo.setCurrentIndex(0)
            return
        index = combo.findData(value)
        # Be forgiving if the DB stores refs as strings/ints interchangeably
        if index < 0 and isinstance(value, str):
            try:
                numeric_value = int(value)
            except ValueError:
                numeric_value = None
            if numeric_value is not None:
                index = combo.findData(numeric_value)
        if index < 0 and isinstance(value, int):
            index = combo.findData(str(value))
        combo.setCurrentIndex(index if index >= 0 else 0)

    # ------------------------------------------------------------------
    # Form state helpers
    # ------------------------------------------------------------------
    def clear_form(self) -> None:
        """Reset all user-editable fields to their defaults."""

        self.id_edit.clear()
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
        self.resource_type_search.clear()
        self.org_combo.setCurrentIndex(-1)
        self.org_combo.clearEditText()
        self.tags_edit.clear()
        self._current_record = None

    def set_vehicle_id(self, vehicle_id: int | str | None) -> None:
        """Change the active vehicle being edited."""

        self._vehicle_id = vehicle_id
        self._pending_vehicle_load = vehicle_id is not None

        if vehicle_id is None:
            self.id_edit.clear()
            self.clear_form()
        else:
            self.id_edit.setText(str(vehicle_id))
            if self._references_loaded:
                self._pending_vehicle_load = False
                self._load_vehicle(vehicle_id)

        self._update_window_title()

    def _update_window_title(self) -> None:
        if self._vehicle_id is None:
            self.setWindowTitle("Add Vehicle")
        else:
            self.setWindowTitle(f"Edit Vehicle {self._vehicle_id}")

    def _update_save_button_state(self) -> None:
        self.save_button.setEnabled(self._references_loaded)

    # ------------------------------------------------------------------
    # Payload collection and validation
    # ------------------------------------------------------------------
    def collect_payload(self) -> dict[str, Any]:
        """Collect the current form values into a database payload."""

        ref_id = self.id_edit.text().strip()
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
            "id": ref_id or None,
            "license_plate": license_plate,
            "vin": vin,
            "year": year_value,
            "make": make_text or None,
            "model": model_text or None,
            "capacity": self.capacity_spin.value(),
            "type_id": self.type_combo.currentData(),
            "status_id": self.status_combo.currentData(),
            "resource_type_id": self.resource_type_search.resource_type_id,
            "tags": tags,
            "organization": self.org_combo.currentText().strip(),
        }
        return payload

    def validate_payload(self, payload: dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate the vehicle ID and any fields that have a value entered."""

        if self._vehicle_id is not None and not payload.get("id"):
            return False, "Vehicle ID is required."

        year_value = payload.get("year")
        if year_value is not None and not (1900 <= year_value <= 2100):
            return False, "Year must be between 1900 and 2100."

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
                response = self._repository.create_vehicle(payload)
                new_id = response.get("id")
                if new_id is not None:
                    self._vehicle_id = new_id
            else:
                response = self._repository.update_vehicle(self._vehicle_id, payload)
                new_id = response.get("id")
                if new_id is not None:
                    self._vehicle_id = new_id
        except LookupError as exc:  # pragma: no cover - UI branch
            logger.error("Failed to save vehicle %s: %s", self._vehicle_id, exc)
            QMessageBox.critical(
                self,
                "Save Failed",
                f"The vehicle could not be found.\n\n{exc}",
            )
            return
        except Exception as exc:  # pragma: no cover - UI branch
            logger.error("Failed to save vehicle %s: %s", self._vehicle_id, exc)
            QMessageBox.critical(
                self,
                "Save Failed",
                self._format_error_message(exc),
            )
            return

        self._current_record = response
        self.id_edit.setText("" if self._vehicle_id is None else str(self._vehicle_id))
        self.vehicleSaved.emit(response)
        self.accept()

    def _format_error_message(self, exc: Exception) -> str:
        return f"Unable to save the vehicle.\n\n{exc}"
