"""CSV import/export helpers for Edit-menu catalog items.

All entities use the MongoDB API via api_client, matching the architecture
rule (UI → API server → MongoDB). Canned Communication Entries is the one
exception that is still SQLite-backed pending its own cutover.

Each IO class exposes:
  - fetch_rows() → list[dict]  (for export)
  - import_row(payload)        (for import, one row at a time)
  - csv_fields                 (column order in the CSV)

Call do_export_csv / do_import_csv from main.py menu handlers; they open
Qt file dialogs and show results to the user.
"""
from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ImportResult:
    inserted: int
    skipped: list[str]
    errors: list[str]

    @property
    def summary(self) -> str:
        lines = [f"Imported: {self.inserted}"]
        if self.skipped:
            lines.append(f"Skipped {len(self.skipped)} duplicate/empty row(s).")
        if self.errors:
            lines.append(f"Errors ({len(self.errors)}):")
            lines.extend(f"  {e}" for e in self.errors[:10])
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class CatalogIO:
    """Descriptor for one Edit-menu entity's CSV import/export."""

    label: str = ""
    csv_fields: list[str] = []

    def fetch_rows(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def import_row(self, payload: dict[str, Any]) -> None:
        raise NotImplementedError

    def map_csv_row(self, raw: dict[str, str]) -> dict[str, Any]:
        norm = {k.strip().lower().replace(" ", "_"): (v or "").strip() for k, v in raw.items()}
        return {f: norm.get(f, "") for f in self.csv_fields}

    def export_csv(self, path: Path) -> Path:
        path = Path(path)
        if not path.suffix:
            path = path.with_suffix(".csv")
        rows = self.fetch_rows()
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=self.csv_fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({f: row.get(f, "") for f in self.csv_fields})
        return path

    def import_csv(self, path: Path) -> ImportResult:
        inserted = 0
        skipped: list[str] = []
        errors: list[str] = []
        with Path(path).open("r", newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames:
                return ImportResult(0, [], ["CSV file has no header row."])
            for idx, raw in enumerate(reader, start=2):
                try:
                    payload = self.map_csv_row(raw)
                    if not any(str(v).strip() for v in payload.values()):
                        skipped.append(f"Row {idx}: empty")
                        continue
                    self.import_row(payload)
                    inserted += 1
                except Exception as exc:
                    errors.append(f"Row {idx}: {exc}")
        return ImportResult(inserted, skipped, errors)


# ---------------------------------------------------------------------------
# API-backed base (MongoDB via api_client)
# ---------------------------------------------------------------------------

class _ApiIO(CatalogIO):
    _list_endpoint: str = ""
    _create_endpoint: str = ""

    def _api(self):
        from utils.api_client import api_client
        return api_client

    def fetch_rows(self) -> list[dict[str, Any]]:
        return self._api().get(self._list_endpoint) or []

    def import_row(self, payload: dict[str, Any]) -> None:
        self._api().post(self._create_endpoint, json=payload)


# ---------------------------------------------------------------------------
# Aircraft — /api/master/aircraft
# ---------------------------------------------------------------------------

class AircraftIO(_ApiIO):
    label = "Aircraft"
    _list_endpoint = "/api/master/aircraft"
    _create_endpoint = "/api/master/aircraft"
    csv_fields = [
        "tail_number", "callsign", "type", "make", "model",
        "base", "status", "organization", "fuel_type",
        "range_nm", "endurance_hr", "cruise_kt",
        "crew_min", "crew_max", "notes",
    ]


# ---------------------------------------------------------------------------
# Canned Communication Entries — /api/master/canned-comm-entries
# ---------------------------------------------------------------------------

class CannedCommEntriesIO(_ApiIO):
    label = "Canned Communication Entries"
    _list_endpoint = "/api/master/canned-comm-entries"
    _create_endpoint = "/api/master/canned-comm-entries"
    csv_fields = [
        "title", "category", "message", "priority",
        "notification_level", "status_update", "is_active",
    ]

    def import_row(self, payload: dict[str, Any]) -> None:
        v = payload.get("is_active", "1")
        payload["is_active"] = str(v).strip().lower() not in ("0", "false", "no")
        payload["notification_level"] = int(payload.get("notification_level") or 0)
        self._api().post(self._create_endpoint, json=payload)


# ---------------------------------------------------------------------------
# Communications Resources (ICS-217) — /api/comms/master-channels
# ---------------------------------------------------------------------------

class CommsResourcesIO(_ApiIO):
    label = "Communications Resources (ICS-217)"
    _list_endpoint = "/api/comms/master-channels"
    _create_endpoint = "/api/comms/master-channels"
    csv_fields = [
        "name", "function", "rx_freq", "tx_freq",
        "rx_tone", "tx_tone", "system", "mode", "notes",
    ]


# ---------------------------------------------------------------------------
# EMS Agencies — MongoDB direct via EMSAgencyRepository
# ---------------------------------------------------------------------------

class EmsAgenciesIO(CatalogIO):
    label = "EMS Agencies"
    csv_fields = [
        "name", "type", "phone", "radio_channel",
        "address", "city", "state", "zip", "lat", "lon",
        "notes", "default_on_206", "is_active",
    ]

    def _repo(self):
        from modules.medical.data.ems_agencies_schema import EMSAgencyRepository
        return EMSAgencyRepository()

    def fetch_rows(self) -> list[dict[str, Any]]:
        return self._repo().list_agencies(include_inactive=True)

    def import_row(self, payload: dict[str, Any]) -> None:
        for bool_field in ("default_on_206", "is_active"):
            v = payload.get(bool_field, "1")
            payload[bool_field] = str(v).strip().lower() not in ("0", "false", "no", "")
        self._repo().create(payload)


# ---------------------------------------------------------------------------
# Equipment — /api/master/equipment
# ---------------------------------------------------------------------------

class EquipmentIO(_ApiIO):
    label = "Equipment"
    _list_endpoint = "/api/master/equipment"
    _create_endpoint = "/api/master/equipment"
    csv_fields = [
        "name", "type", "serial_number",
        "condition", "condition_status", "notes",
    ]


# ---------------------------------------------------------------------------
# Hazard Type Library — /api/hazard-types
# ---------------------------------------------------------------------------

class HazardTypesIO(_ApiIO):
    label = "Hazard Type Library"
    _list_endpoint = "/api/hazard-types"
    _create_endpoint = "/api/hazard-types"
    csv_fields = [
        "name", "category", "default_risk_level", "source",
        "typical_likelihood", "description", "is_active",
    ]

    def fetch_rows(self) -> list[dict[str, Any]]:
        rows = self._api().get(self._list_endpoint, params={"include_inactive": "true"}) or []
        return [
            {
                "name": r.get("name", ""),
                "category": r.get("category", ""),
                "default_risk_level": r.get("default_risk_level", ""),
                "source": r.get("source", ""),
                "typical_likelihood": r.get("typical_likelihood", ""),
                "description": r.get("description", ""),
                "is_active": r.get("is_active", True),
            }
            for r in rows
        ]

    def import_row(self, payload: dict[str, Any]) -> None:
        v = payload.get("is_active", "1")
        payload["is_active"] = str(v).strip().lower() not in ("0", "false", "no")
        self._api().post(self._create_endpoint, json=payload)


# ---------------------------------------------------------------------------
# Hospitals — /api/master/hospitals
# ---------------------------------------------------------------------------

class HospitalsIO(_ApiIO):
    label = "Hospitals"
    _list_endpoint = "/api/master/hospitals"
    _create_endpoint = "/api/master/hospitals"
    csv_fields = [
        "name", "address", "contact_name", "phone_er", "phone_switchboard",
        "travel_time_min", "helipad", "trauma_level", "burn_center",
        "pediatric_capability", "notes", "lat", "lon",
    ]


# ---------------------------------------------------------------------------
# Objectives (master templates) — /api/master/objective-templates
# ---------------------------------------------------------------------------

class ObjectivesIO(_ApiIO):
    label = "Objectives"
    _list_endpoint = "/api/master/objective-templates"
    _create_endpoint = "/api/master/objective-templates"
    csv_fields = [
        "code", "title", "description", "default_section",
        "priority", "tags",
    ]

    def fetch_rows(self) -> list[dict[str, Any]]:
        rows = self._api().get(self._list_endpoint, params={"include_archived": "true"}) or []
        return [
            {
                "code": r.get("code", ""),
                "title": r.get("title", ""),
                "description": r.get("description", ""),
                "default_section": r.get("default_section", ""),
                "priority": r.get("priority", "Normal"),
                "tags": ";".join(r.get("tags") or []),
            }
            for r in rows
        ]

    def map_csv_row(self, raw: dict[str, str]) -> dict[str, Any]:
        norm = {k.strip().lower().replace(" ", "_"): (v or "").strip() for k, v in raw.items()}
        tags_raw = norm.get("tags", "")
        tags = [t.strip() for t in tags_raw.split(";") if t.strip()] if tags_raw else []
        return {
            "code": norm.get("code", ""),
            "title": norm.get("title", ""),
            "description": norm.get("description", ""),
            "default_section": norm.get("default_section", ""),
            "priority": norm.get("priority", "Normal"),
            "tags": tags,
        }


# ---------------------------------------------------------------------------
# Personnel — /api/master/personnel
# ---------------------------------------------------------------------------

class PersonnelIO(_ApiIO):
    label = "Personnel"
    _list_endpoint = "/api/master/personnel"
    _create_endpoint = "/api/master/personnel"
    csv_fields = [
        "name", "callsign", "role", "phone", "email",
        "organization", "qualifications",
    ]

    def fetch_rows(self) -> list[dict[str, Any]]:
        rows = self._api().get(self._list_endpoint, params={"limit": 2000}) or []
        return [
            {
                "name": r.get("name", ""),
                "callsign": r.get("callsign", ""),
                "role": r.get("role", ""),
                "phone": r.get("phone", ""),
                "email": r.get("email", ""),
                "organization": r.get("organization", ""),
                "qualifications": r.get("qualifications", ""),
            }
            for r in rows
        ]


# ---------------------------------------------------------------------------
# Resource Type Library — delegate to existing resource_type_io
# ---------------------------------------------------------------------------

class ResourceTypesIO(CatalogIO):
    """Thin wrapper delegating to the existing resource_type_io module."""

    label = "Resource Type Library"
    csv_fields = []

    def export_csv(self, path: Path) -> Path:
        from modules.admin.resource_types.data.resource_type_repository import (
            ApiResourceTypeRepository,
        )
        return ApiResourceTypeRepository().export_csv(path)

    def import_csv(self, path: Path) -> ImportResult:
        from modules.admin.resource_types.data.resource_type_repository import (
            ApiResourceTypeRepository,
        )
        from modules.common.models.lookup_models import ImportResult as _IR
        r: _IR = ApiResourceTypeRepository().import_csv(path)
        return ImportResult(r.inserted, r.skipped_duplicates, r.errors)

    def fetch_rows(self) -> list[dict[str, Any]]:
        return []

    def import_row(self, payload: dict[str, Any]) -> None:
        pass


# ---------------------------------------------------------------------------
# Safety Analysis Templates — /api/master/safety-templates
# ---------------------------------------------------------------------------

class SafetyTemplatesIO(_ApiIO):
    label = "Safety Analysis Templates"
    _list_endpoint = "/api/master/safety-templates"
    _create_endpoint = "/api/master/safety-templates"
    csv_fields = [
        "name", "description", "scenario_type", "notes", "is_active",
    ]

    def fetch_rows(self) -> list[dict[str, Any]]:
        rows = self._api().get(self._list_endpoint, params={"include_inactive": "true"}) or []
        return [
            {
                "name": r.get("name", ""),
                "description": r.get("description", ""),
                "scenario_type": r.get("scenario_type", ""),
                "notes": r.get("notes", ""),
                "is_active": r.get("is_active", True),
            }
            for r in rows
        ]

    def import_row(self, payload: dict[str, Any]) -> None:
        v = payload.get("is_active", "1")
        payload["is_active"] = str(v).strip().lower() not in ("0", "false", "no")
        self._api().post(self._create_endpoint, json=payload)


# ---------------------------------------------------------------------------
# Task Types — ApiTaskTypesRepository (MongoDB)
# ---------------------------------------------------------------------------

class TaskTypesIO(CatalogIO):
    label = "Task Types"
    csv_fields = ["name", "category", "default_priority", "description", "is_active"]

    def _repo(self):
        from modules.common.models.lookup_models import ApiTaskTypesRepository
        return ApiTaskTypesRepository()

    def export_csv(self, path: Path) -> Path:
        return self._repo().export_csv(path)

    def import_csv(self, path: Path) -> ImportResult:
        from modules.common.models.lookup_models import ImportResult as _IR
        r: _IR = self._repo().import_csv(path)
        return ImportResult(r.inserted, r.skipped_duplicates, r.errors)

    def fetch_rows(self) -> list[dict[str, Any]]:
        return self._repo().list(include_inactive=True)

    def import_row(self, payload: dict[str, Any]) -> None:
        self._repo().create(payload)


# ---------------------------------------------------------------------------
# Team Types — ApiTeamTypesRepository (MongoDB)
# ---------------------------------------------------------------------------

class TeamTypesIO(CatalogIO):
    label = "Team Types"
    csv_fields = ["name", "category", "description", "is_active"]

    def _repo(self):
        from modules.common.models.lookup_models import ApiTeamTypesRepository
        return ApiTeamTypesRepository()

    def export_csv(self, path: Path) -> Path:
        return self._repo().export_csv(path)

    def import_csv(self, path: Path) -> ImportResult:
        from modules.common.models.lookup_models import ImportResult as _IR
        r: _IR = self._repo().import_csv(path)
        return ImportResult(r.inserted, r.skipped_duplicates, r.errors)

    def fetch_rows(self) -> list[dict[str, Any]]:
        return self._repo().list(include_inactive=True)

    def import_row(self, payload: dict[str, Any]) -> None:
        self._repo().create(payload)


# ---------------------------------------------------------------------------
# Units and Organizations — /api/master/organizations
# ---------------------------------------------------------------------------

class UnitsOrganizationsIO(_ApiIO):
    label = "Units and Organizations"
    _list_endpoint = "/api/master/organizations"
    _create_endpoint = "/api/master/organizations"
    csv_fields = [
        "name", "short_name", "org_type", "parent_name",
        "address", "phone", "email", "notes",
    ]

    def fetch_rows(self) -> list[dict[str, Any]]:
        rows = self._api().get(self._list_endpoint) or []
        return [
            {
                "name": r.get("name", ""),
                "short_name": r.get("short_name", ""),
                "org_type": r.get("type") or r.get("org_type", ""),
                "parent_name": r.get("parent_name", ""),
                "address": r.get("address", ""),
                "phone": r.get("phone", ""),
                "email": r.get("email", ""),
                "notes": r.get("notes", ""),
            }
            for r in rows
        ]


# ---------------------------------------------------------------------------
# Vehicles — /api/master/vehicles
# ---------------------------------------------------------------------------

class VehiclesIO(_ApiIO):
    label = "Vehicles"
    _list_endpoint = "/api/master/vehicles"
    _create_endpoint = "/api/master/vehicles"
    csv_fields = [
        "license_plate", "vin", "year", "make", "model",
        "capacity", "type_id", "status_id", "organization",
    ]


# ---------------------------------------------------------------------------
# Generic Qt dialog helpers
# ---------------------------------------------------------------------------

def do_export_csv(io: CatalogIO, parent) -> None:
    """Open a save-file dialog and export the given catalog to CSV."""
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    path, _ = QFileDialog.getSaveFileName(
        parent,
        f"Export {io.label}",
        f"{io.label.replace(' ', '_')}.csv",
        "CSV Files (*.csv);;All Files (*)",
    )
    if not path:
        return
    try:
        out = io.export_csv(Path(path))
        QMessageBox.information(parent, "Export Complete", f"Exported to:\n{out}")
    except Exception as exc:
        log.exception("Export failed for %s", io.label)
        QMessageBox.critical(parent, "Export Failed", str(exc))


def do_import_csv(io: CatalogIO, parent) -> None:
    """Open an open-file dialog and import CSV rows into the given catalog."""
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    path, _ = QFileDialog.getOpenFileName(
        parent,
        f"Import {io.label}",
        "",
        "CSV Files (*.csv);;All Files (*)",
    )
    if not path:
        return
    try:
        result = io.import_csv(Path(path))
        QMessageBox.information(parent, "Import Complete", result.summary)
    except Exception as exc:
        log.exception("Import failed for %s", io.label)
        QMessageBox.critical(parent, "Import Failed", str(exc))
