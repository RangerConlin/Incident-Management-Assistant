"""API-backed service layer for the Logistics Check-In window."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class FieldSpec:
    """Metadata describing a field exposed in the 'new record' dialog."""

    name: str
    label: str
    required: bool = False
    placeholder: Optional[str] = None


@dataclass(frozen=True)
class EntityConfig:
    """Configuration for a master/incident entity pair."""

    key: str
    title: str
    master_table: str
    incident_table: str
    id_column: str
    sort_column: str
    display_columns: Tuple[Tuple[str, str], ...]
    form_fields: Tuple[FieldSpec, ...]
    id_field: Optional[FieldSpec] = None
    autoincrement: bool = True


ENTITY_CONFIG: Dict[str, EntityConfig] = {
    "personnel": EntityConfig(
        key="personnel",
        title="Personnel",
        master_table="personnel",
        incident_table="personnel",
        id_column="id",
        sort_column="name",
        display_columns=(
            ("id", "ID"),
            ("name", "Name"),
            ("role", "Role"),
            ("rank", "Rank"),
            ("callsign", "Callsign"),
        ),
        form_fields=(
            FieldSpec("name", "Name", required=True),
            FieldSpec("rank", "Rank"),
            FieldSpec("role", "Role"),
            FieldSpec("callsign", "Callsign"),
            FieldSpec("phone", "Phone"),
        ),
        id_field=FieldSpec("id", "Personnel ID", required=True, placeholder="e.g., 10001"),
        autoincrement=True,
    ),
    "vehicle": EntityConfig(
        key="vehicle",
        title="Vehicle",
        master_table="vehicles",
        incident_table="vehicles",
        id_column="id",
        sort_column="id",
        display_columns=(
            ("id", "ID"),
            ("make", "Make"),
            ("model", "Model"),
            ("resource_type_id", "Resource Type"),
            ("status_id", "Status"),
        ),
        form_fields=(
            FieldSpec("make", "Make"),
            FieldSpec("model", "Model"),
            FieldSpec("license_plate", "License Plate"),
            FieldSpec("resource_type_id", "Resource Type"),
            FieldSpec("status_id", "Status"),
        ),
        id_field=FieldSpec("id", "Vehicle ID", required=True),
        autoincrement=False,
    ),
    "equipment": EntityConfig(
        key="equipment",
        title="Equipment",
        master_table="equipment",
        incident_table="equipment",
        id_column="id",
        sort_column="name",
        display_columns=(
            ("id", "ID"),
            ("name", "Name"),
            ("type", "Type"),
            ("resource_type_id", "Resource Type"),
            ("condition", "Condition"),
        ),
        form_fields=(
            FieldSpec("name", "Name", required=True),
            FieldSpec("type", "Type"),
            FieldSpec("serial_number", "Serial Number"),
            FieldSpec("resource_type_id", "Resource Type"),
            FieldSpec("condition", "Condition"),
        ),
        autoincrement=True,
    ),
    "aircraft": EntityConfig(
        key="aircraft",
        title="Aircraft",
        master_table="aircraft",
        incident_table="aircraft",
        id_column="id",
        sort_column="tail_number",
        display_columns=(
            ("id", "ID"),
            ("tail_number", "Tail Number"),
            ("type", "Type"),
            ("status", "Status"),
        ),
        form_fields=(
            FieldSpec("tail_number", "Tail Number", required=True),
            FieldSpec("type", "Type", required=True),
            FieldSpec("callsign", "Callsign"),
            FieldSpec("base", "Base Location"),
        ),
        autoincrement=True,
    ),
}

ENTITY_ORDER: Tuple[str, ...] = ("personnel", "vehicle", "equipment", "aircraft")

# Master API base paths by entity type
_MASTER_BASE: Dict[str, str] = {
    "personnel": "/api/master/personnel",
    "vehicle": "/api/master/vehicles",
    "equipment": "/api/master/equipment",
    "aircraft": "/api/master/aircraft",
}


def _client():
    from utils.api_client import api_client
    return api_client


def _incident_base(incident_id: str) -> str:
    return f"/api/incidents/{incident_id}/resources"


def _incident_id() -> Optional[str]:
    from utils import incident_context
    return incident_context.get_active_incident_id()


def _get_config(entity_type: str) -> EntityConfig:
    try:
        return ENTITY_CONFIG[entity_type]
    except KeyError as exc:
        raise ValueError(f"Unknown entity type: {entity_type}") from exc


def iter_entity_configs() -> Iterable[EntityConfig]:
    for key in ENTITY_ORDER:
        yield ENTITY_CONFIG[key]


def get_entity_config(entity_type: str) -> EntityConfig:
    return _get_config(entity_type)


class CheckInService:
    """API-backed facade that manages master and incident resource check-in."""

    def _checked_in_ids(self, entity_type: str) -> set[str]:
        incident_id = _incident_id()
        if not incident_id:
            return set()
        try:
            ids = _client().get(
                f"{_incident_base(incident_id)}/checked-ids",
                params={"resource_type": entity_type},
            ) or []
            return {str(i) for i in ids}
        except Exception:
            return set()

    def _mark_checked_in(self, entity_type: str, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        config = _get_config(entity_type)
        checked = self._checked_in_ids(entity_type)
        for r in records:
            identifier = r.get(config.id_column)
            r["_checked_in"] = str(identifier) in checked if identifier is not None else False
        return records

    def list_master_records(self, entity_type: str) -> List[Dict[str, Any]]:
        base = _MASTER_BASE[entity_type]
        try:
            records = _client().get(base) or []
        except Exception:
            return []
        return self._mark_checked_in(entity_type, records)

    def search_master_records(
        self, entity_type: str, query: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        base = _MASTER_BASE[entity_type]
        try:
            records = _client().get(base, params={"search": query, "limit": limit}) or []
        except Exception:
            return []
        return self._mark_checked_in(entity_type, records)

    def create_master_record(self, entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        config = _get_config(entity_type)
        base = _MASTER_BASE[entity_type]

        # Validate required fields
        if config.id_field is not None:
            supplied = data.get(config.id_column)
            supplied_str = supplied.strip() if isinstance(supplied, str) else str(supplied) if supplied is not None else ""
            if config.id_field.required and not supplied_str:
                raise ValueError(f"{config.id_field.label} is required")

        for field in config.form_fields:
            raw = data.get(field.name)
            text = raw.strip() if isinstance(raw, str) else raw
            if field.required and not text:
                raise ValueError(f"{field.label} is required")

        try:
            doc = _client().post(base, json=data)
        except Exception as exc:
            raise ValueError(str(exc)) from exc

        doc["_checked_in"] = False
        return doc

    def check_in(
        self,
        entity_type: str,
        record_id: Any,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        incident_id = _incident_id()
        if not incident_id:
            raise RuntimeError("No active incident")

        try:
            doc = _client().post(
                f"{_incident_base(incident_id)}/{entity_type}/{record_id}",
                json=overrides or {},
            )
        except Exception as exc:
            raise ValueError(str(exc)) from exc

        doc["_checked_in"] = True

        # For personnel check-ins, also create a roster record
        if entity_type == "personnel":
            try:
                from . import repository as ci_repo
                from .models import CheckInRecord, CIStatus, PersonnelStatus, Location
                from datetime import datetime
                now_iso = datetime.now().astimezone().isoformat(timespec="seconds")
                pid = str(doc.get("id") or doc.get("person_id") or record_id)
                if pid:
                    existing = None
                    try:
                        existing = ci_repo.fetch_checkin(pid)
                    except Exception:
                        pass
                    if existing is None:
                        rec = CheckInRecord(
                            person_id=pid,
                            ci_status=CIStatus.CHECKED_IN,
                            personnel_status=PersonnelStatus.AVAILABLE,
                            arrival_time=now_iso,
                            location=Location.ICP,
                            incident_callsign=doc.get("callsign"),
                            incident_phone=doc.get("phone") or doc.get("contact"),
                            team_id=None,
                            role_on_team=doc.get("role") or doc.get("primary_role"),
                        )
                    else:
                        rec = existing
                    try:
                        ci_repo.save_checkin(rec)
                    except Exception:
                        pass
            except Exception:
                pass

        return doc


_service: Optional[CheckInService] = None


def get_service() -> CheckInService:
    global _service
    if _service is None:
        _service = CheckInService()
    return _service


def reset_service() -> None:
    global _service
    _service = None


__all__ = [
    "CheckInService",
    "EntityConfig",
    "FieldSpec",
    "ENTITY_ORDER",
    "ENTITY_CONFIG",
    "get_entity_config",
    "iter_entity_configs",
    "get_service",
    "reset_service",
]
