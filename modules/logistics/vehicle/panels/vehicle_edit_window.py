"""Vehicle inventory editing dialog implemented with Qt widgets."""

from __future__ import annotations

import logging
import sqlite3
from collections import OrderedDict
from pathlib import Path
from typing import Any, Optional

from utils.db import get_master_conn
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


class VehicleRepository:
    """Persistence helper that reads and writes vehicle records in SQLite."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        self._db_path: Optional[Path] = Path(db_path) if db_path else None

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        if self._db_path is not None:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            return conn
        conn = get_master_conn()
        conn.row_factory = sqlite3.Row
        return conn

    def _table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        query = "SELECT 1 FROM sqlite_master WHERE type='table' AND lower(name)=? LIMIT 1"
        row = conn.execute(query, (table_name.lower(),)).fetchone()
        return row is not None

    # ------------------------------------------------------------------
    # Reference data
    # ------------------------------------------------------------------
    def list_vehicles(self, search_text: str | None = None) -> list[dict[str, Any]]:
        """Return vehicles from the master database, optionally filtered."""

        if search_text is not None:
            normalized = search_text.strip().lower()
            search_text = normalized or None

        conn = self._connect()
        try:
            base_query = (
                """
                SELECT id, vin, license_plate, year, make, model, capacity,
                       type_id, status_id, tags, organization
                FROM vehicles
                """
            )
            params: list[Any] = []
            if search_text:
                term = f"%{search_text}%"
                filters = " OR ".join(
                    [
                        "lower(COALESCE(vin, '')) LIKE ?",
                        "lower(COALESCE(license_plate, '')) LIKE ?",
                        "lower(COALESCE(make, '')) LIKE ?",
                        "lower(COALESCE(model, '')) LIKE ?",
                        "lower(COALESCE(tags, '')) LIKE ?",
                    ]
                )
                base_query += f"WHERE {filters}\n"
                params.extend([term] * 5)

            base_query += (
                """
                ORDER BY
                    CASE WHEN TRIM(COALESCE(make, '')) = '' THEN 1 ELSE 0 END,
                    lower(COALESCE(make, '')),
                    lower(COALESCE(model, '')),
                    CAST(id AS INTEGER)
                """
            )

            rows = conn.execute(base_query, tuple(params)).fetchall()
        finally:
            conn.close()

        return [self._row_to_dict(row) for row in rows]

    def list_vehicle_types(self) -> list[dict[str, Any]]:
        """Return available vehicle type options."""

        conn = self._connect()
        try:
            for table_name in ("vehicle_types", "vehicle_type"):
                if self._table_exists(conn, table_name):
                    rows = conn.execute(
                        f"SELECT id, name FROM {table_name} ORDER BY name"
                    ).fetchall()
                    return [
                        {"id": row["id"], "name": row["name"] or str(row["id"])}
                        for row in rows
                    ]

            rows = conn.execute(
                """
                SELECT DISTINCT type_id
                FROM vehicles
                WHERE TRIM(COALESCE(type_id, '')) != ''
                ORDER BY type_id
                """
            ).fetchall()
            entries = []
            for row in rows:
                value = row["type_id"]
                if value in (None, ""):
                    continue
                label = str(value).strip()
                entries.append({"id": value, "name": label or str(value)})
        finally:
            conn.close()

        if not entries:
            entries = [{"id": choice, "name": choice} for choice in DEFAULT_TYPE_CHOICES]
        return entries

    def list_statuses(self) -> list[dict[str, Any]]:
        """Return available vehicle status options."""

        conn = self._connect()
        try:
            for table_name in ("vehicle_statuses", "statuses"):
                if self._table_exists(conn, table_name):
                    rows = conn.execute(
                        f"SELECT id, name FROM {table_name} ORDER BY name"
                    ).fetchall()
                    return [
                        {"id": row["id"], "name": row["name"] or str(row["id"])}
                        for row in rows
                    ]

            rows = conn.execute(
                """
                SELECT DISTINCT status_id
                FROM vehicles
                WHERE TRIM(COALESCE(status_id, '')) != ''
                ORDER BY status_id
                """
            ).fetchall()
            options = OrderedDict()
            for row in rows:
                value = row["status_id"]
                if value in (None, ""):
                    continue
                label = str(value).strip() or str(value)
                options.setdefault(value, label)
        finally:
            conn.close()

        for default in DEFAULT_STATUS_CHOICES:
            options.setdefault(default, default)
        return [{"id": key, "name": label} for key, label in options.items()]

    # ------------------------------------------------------------------
    # CRUD helpers
    # ------------------------------------------------------------------
    def delete_vehicle(self, vehicle_id: int | str) -> None:
        """Remove a vehicle from the catalog."""

        conn = self._connect()
        try:
            cur = conn.execute(
                "DELETE FROM vehicles WHERE id = ?",
                (str(vehicle_id),),
            )
            if cur.rowcount == 0:
                raise LookupError(f"Vehicle {vehicle_id} does not exist")
            conn.commit()
        finally:
            conn.close()

    def fetch_vehicle(self, vehicle_id: int | str) -> Optional[dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT id, vin, license_plate, year, make, model, capacity,
                       type_id, status_id, tags, organization
                FROM vehicles
                WHERE id = ?
                """,
                (str(vehicle_id),),
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            return None
        return self._row_to_dict(row)

    def create_vehicle(self, payload: dict[str, Any]) -> dict[str, Any]:
        conn = self._connect()
        try:
            new_id = self._generate_new_id(conn)
            params = self._build_params(payload)
            params.insert(0, new_id)
            conn.execute(
                """
                INSERT INTO vehicles (
                    id, vin, license_plate, year, make, model,
                    capacity, type_id, status_id, tags, organization
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuple(params),
            )
            conn.commit()
        finally:
            conn.close()

        record = self.fetch_vehicle(new_id)
        if record is None:  # pragma: no cover - defensive
            raise RuntimeError("Vehicle creation failed")
        return record

    def update_vehicle(self, vehicle_id: int | str, payload: dict[str, Any]) -> dict[str, Any]:
        conn = self._connect()
        try:
            params = self._build_params(payload)
            params.append(str(vehicle_id))
            cur = conn.execute(
                """
                UPDATE vehicles
                SET vin = ?,
                    license_plate = ?,
                    year = ?,
                    make = ?,
                    model = ?,
                    capacity = ?,
                    type_id = ?,
                    status_id = ?,
                    tags = ?,
                    organization = ?
                WHERE id = ?
                """,
                tuple(params),
            )
            if cur.rowcount == 0:
                raise LookupError(f"Vehicle {vehicle_id} does not exist")
            conn.commit()
        finally:
            conn.close()

        record = self.fetch_vehicle(vehicle_id)
        if record is None:  # pragma: no cover - defensive
            raise RuntimeError("Vehicle update failed")
        return record

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------
    def _generate_new_id(self, conn: sqlite3.Connection) -> str:
        row = conn.execute(
            "SELECT MAX(CAST(id AS INTEGER)) FROM vehicles WHERE CAST(id AS INTEGER) IS NOT NULL"
        ).fetchone()
        next_id = (row[0] or 0) + 1
        # Ensure uniqueness in case of non-numeric identifiers.
        while conn.execute("SELECT 1 FROM vehicles WHERE id = ?", (str(next_id),)).fetchone():
            next_id += 1
        return str(next_id)

    def _build_params(self, payload: dict[str, Any]) -> list[Any]:
        tags = payload.get("tags") or []
        if isinstance(tags, str):
            tags_list = [part.strip() for part in tags.split(",") if part.strip()]
        else:
            tags_list = list(tags)
        tags_value = ", ".join(tags_list) if tags_list else None

        make_value = payload.get("make") or None
        model_value = payload.get("model") or None
        organization_value = payload.get("organization")

        params: list[Any] = [
            payload.get("vin") or None,
            payload.get("license_plate") or None,
            payload.get("year"),
            make_value,
            model_value,
            payload.get("capacity", 0),
            self._normalize_reference(payload.get("type_id")),
            self._normalize_reference(payload.get("status_id")),
            tags_value,
            organization_value,
        ]
        return params

    def _normalize_reference(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        record = dict(row)
        identifier = record.get("id")
        if isinstance(identifier, str):
            try:
                record["id"] = int(identifier)
            except ValueError:
                pass

        tags_value = record.get("tags")
        if isinstance(tags_value, str):
            record["tags"] = [
                part.strip() for part in tags_value.split(",") if part.strip()
            ]
        elif tags_value is None:
            record["tags"] = []

        return record


class VehicleEditDialog(QDialog):
    """Modal dialog used to add or edit a single vehicle record."""

    vehicleSaved = Signal(dict)

    def __init__(
        self,
        vehicle_id: int | None = None,
        repository: Optional[VehicleRepository] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._repository = repository or VehicleRepository()
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

    def _load_vehicle(self, vehicle_id: int) -> None:
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
        """Collect the current form values into a database payload."""

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
            "organization": (
                self._current_record.get("organization")
                if self._current_record
                else None
            ),
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

        type_id = payload.get("type_id")
        if type_id is None or (isinstance(type_id, str) and not type_id.strip()):
            return False, "Please select a vehicle type."
        status_id = payload.get("status_id")
        if status_id is None or (isinstance(status_id, str) and not status_id.strip()):
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
                response = self._repository.create_vehicle(payload)
                new_id = response.get("id")
                if isinstance(new_id, int):
                    self._vehicle_id = new_id
            else:
                response = self._repository.update_vehicle(self._vehicle_id, payload)
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
        self.vehicleSaved.emit(response)
        self.accept()

    def _format_error_message(self, exc: Exception) -> str:
        """Generate a user-friendly description of a persistence error."""

        if isinstance(exc, sqlite3.Error):
            parts = [str(part) for part in exc.args if part]
            message = " ".join(parts)
            if message:
                return f"Unable to save the vehicle.\n\n{message}"
        return f"Unable to save the vehicle.\n\n{exc}"
