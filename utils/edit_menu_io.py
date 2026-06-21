"""CSV import/export helpers for Edit-menu catalog items.

Each IO class handles one entity type. Call do_export_csv / do_import_csv
from main.py menu handlers; the helpers open file dialogs and display results.
"""
from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_MASTER_DB = "data/master.db"


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
# SQLite catalog base (uses models.master_catalog.make_service)
# ---------------------------------------------------------------------------

class _SqliteIO(CatalogIO):
    entity_key: str = ""

    def _svc(self):
        from models.master_catalog import make_service
        return make_service(_MASTER_DB, self.entity_key)

    def fetch_rows(self) -> list[dict[str, Any]]:
        return self._svc().list()

    def import_row(self, payload: dict[str, Any]) -> None:
        self._svc().create(payload)


# ---------------------------------------------------------------------------
# Aircraft
# ---------------------------------------------------------------------------

class AircraftIO(_SqliteIO):
    label = "Aircraft"
    entity_key = "aircraft"
    csv_fields = [
        "tail_number", "callsign", "type", "make_model",
        "capacity", "status", "base_location", "capabilities", "notes",
    ]


# ---------------------------------------------------------------------------
# Canned Communication Entries
# ---------------------------------------------------------------------------

class CannedCommEntriesIO(_SqliteIO):
    label = "Canned Communication Entries"
    entity_key = "canned_comm_entries"
    csv_fields = [
        "title", "category", "message", "priority",
        "notification_level", "status_update", "is_active",
    ]


# ---------------------------------------------------------------------------
# Communications Resources (ICS-217) — MongoDB via API
# ---------------------------------------------------------------------------

class CommsResourcesIO(CatalogIO):
    label = "Communications Resources (ICS-217)"
    csv_fields = [
        "name", "function", "rx_freq", "tx_freq",
        "rx_tone", "tx_tone", "system", "mode", "notes",
    ]

    def fetch_rows(self) -> list[dict[str, Any]]:
        from utils.api_client import api_client
        return api_client.get("/api/comms/master-channels") or []

    def import_row(self, payload: dict[str, Any]) -> None:
        from utils.api_client import api_client
        api_client.post("/api/comms/master-channels", json=payload)


# ---------------------------------------------------------------------------
# EMS Agencies — MongoDB direct
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
# Equipment
# ---------------------------------------------------------------------------

class EquipmentIO(_SqliteIO):
    label = "Equipment"
    entity_key = "equipment"
    csv_fields = [
        "name", "type", "serial_number",
        "condition", "condition_status", "notes",
    ]


# ---------------------------------------------------------------------------
# Hazard Type Library — MongoDB via API
# ---------------------------------------------------------------------------

class HazardTypesIO(CatalogIO):
    label = "Hazard Type Library"
    csv_fields = [
        "name", "category", "default_risk_level", "source",
        "typical_likelihood", "description", "is_active",
    ]

    def fetch_rows(self) -> list[dict[str, Any]]:
        from modules.admin.hazard_types.data.hazard_type_repository import ApiHazardTypeRepository
        repo = ApiHazardTypeRepository()
        raw = repo.list_hazard_types({"include_inactive": True})
        out = []
        for r in raw:
            out.append({
                "name": r.get("name", ""),
                "category": r.get("category", ""),
                "default_risk_level": r.get("default_risk_level", ""),
                "source": r.get("source", ""),
                "typical_likelihood": r.get("typical_likelihood", ""),
                "description": r.get("description", ""),
                "is_active": r.get("is_active", True),
            })
        return out

    def import_row(self, payload: dict[str, Any]) -> None:
        from utils.api_client import api_client
        v = payload.get("is_active", "1")
        payload["is_active"] = str(v).strip().lower() not in ("0", "false", "no")
        api_client.post("/api/hazard-types", json=payload)


# ---------------------------------------------------------------------------
# Hospitals
# ---------------------------------------------------------------------------

class HospitalsIO(_SqliteIO):
    label = "Hospitals"
    entity_key = "hospitals"
    csv_fields = [
        "name", "address", "contact_name", "phone_er", "phone_switchboard",
        "travel_time_min", "helipad", "trauma_level", "burn_center",
        "pediatric_capability", "notes", "lat", "lon",
    ]


# ---------------------------------------------------------------------------
# Objectives (master template list)
# ---------------------------------------------------------------------------

class ObjectivesIO(_SqliteIO):
    label = "Objectives"
    entity_key = "incident_objectives"
    csv_fields = [
        "description", "priority", "status", "section", "customer",
    ]


# ---------------------------------------------------------------------------
# Personnel
# ---------------------------------------------------------------------------

class PersonnelIO(_SqliteIO):
    label = "Personnel"
    entity_key = "personnel"
    csv_fields = ["name", "callsign", "role", "phone", "email"]


# ---------------------------------------------------------------------------
# Resource Type Library — delegate to existing resource_type_io
# ---------------------------------------------------------------------------

class ResourceTypesIO(CatalogIO):
    """Thin wrapper that delegates to the existing resource_type_io module."""

    label = "Resource Type Library"
    csv_fields = []  # io module manages its own fields

    def export_csv(self, path: Path) -> Path:
        from modules.admin.resource_types.data.resource_type_repository import (
            ApiResourceTypeRepository,
        )
        repo = ApiResourceTypeRepository()
        return repo.export_csv(path)

    def import_csv(self, path: Path) -> ImportResult:
        from modules.admin.resource_types.data.resource_type_repository import (
            ApiResourceTypeRepository,
        )
        from modules.common.models.lookup_models import ImportResult as _IR
        repo = ApiResourceTypeRepository()
        r: _IR = repo.import_csv(path)
        return ImportResult(r.inserted, r.skipped_duplicates, r.errors)

    def fetch_rows(self) -> list[dict[str, Any]]:
        return []

    def import_row(self, payload: dict[str, Any]) -> None:
        pass


# ---------------------------------------------------------------------------
# Safety Analysis Templates
# ---------------------------------------------------------------------------

class SafetyTemplatesIO(_SqliteIO):
    label = "Safety Analysis Templates"
    entity_key = "safety_templates"
    csv_fields = [
        "name", "operational_context", "hazard",
        "controls", "residual_risk", "ppe", "notes",
    ]


# ---------------------------------------------------------------------------
# Task Types — MongoDB via ApiTaskTypesRepository
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
# Team Types — MongoDB via ApiTeamTypesRepository
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
# Units and Organizations — MongoDB via API
# ---------------------------------------------------------------------------

class UnitsOrganizationsIO(CatalogIO):
    label = "Units and Organizations"
    csv_fields = [
        "name", "short_name", "org_type", "parent_name",
        "address", "phone", "email", "notes",
    ]

    def fetch_rows(self) -> list[dict[str, Any]]:
        from modules.personnel.units_organizations.models.repository import (
            UnitsOrganizationsRepository,
        )
        repo = UnitsOrganizationsRepository()
        orgs = repo.list_organizations(include_inactive=True)
        out = []
        for o in orgs:
            out.append({
                "name": o.get("name", ""),
                "short_name": o.get("short_name", ""),
                "org_type": o.get("type") or o.get("org_type", ""),
                "parent_name": o.get("parent_name", ""),
                "address": o.get("address", ""),
                "phone": o.get("phone", ""),
                "email": o.get("email", ""),
                "notes": o.get("notes", ""),
            })
        return out

    def import_row(self, payload: dict[str, Any]) -> None:
        from utils.api_client import api_client
        payload.setdefault("is_active", True)
        api_client.post("/api/master/organizations", json=payload)


# ---------------------------------------------------------------------------
# Vehicles
# ---------------------------------------------------------------------------

class VehiclesIO(_SqliteIO):
    label = "Vehicles"
    entity_key = "vehicles"
    csv_fields = [
        "license_plate", "vin", "year", "make", "model",
        "capacity", "organization",
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
