"""API-backed service layer for the Logistics Check-In window."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple


logger = logging.getLogger(__name__)

CHECKED_IN_STATUSES = {
    "Available",
    "Assigned",
    "Out of Service",
    "Preparing for Demobilization",
    "Checked In",
}
ASSIGNED_HINT_FIELDS = (
    "team_id",
    "current_task_id",
    "current_assignment",
    "operational_unit_id",
    "assignment",
    "assigned_driver",
    "responsible_person_id",
    "responsible_team_id",
)


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
        id_column="person_record",
        sort_column="name",
        display_columns=(
            ("person_id", "ID"),
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
        id_field=None,
        autoincrement=True,
    ),
    "vehicle": EntityConfig(
        key="vehicle",
        title="Vehicle",
        master_table="vehicles",
        incident_table="vehicles",
        id_column="vehicle_record",
        sort_column="vehicle_id",
        display_columns=(
            ("vehicle_id", "ID"),
            ("make", "Make"),
            ("model", "Model"),
            ("resource_type_id", "Resource Type"),
            ("status_id", "Status"),
        ),
        form_fields=(
            FieldSpec("vehicle_id", "Vehicle ID", required=True, placeholder="e.g., Engine 2"),
            FieldSpec("make", "Make"),
            FieldSpec("model", "Model"),
            FieldSpec("license_plate", "License Plate"),
            FieldSpec("resource_type_id", "Resource Type"),
            FieldSpec("status_id", "Status"),
        ),
        id_field=FieldSpec("vehicle_id", "Vehicle ID", required=True),
        autoincrement=False,
    ),
    "equipment": EntityConfig(
        key="equipment",
        title="Equipment",
        master_table="equipment",
        incident_table="equipment",
        id_column="equipment_record",
        sort_column="name",
        display_columns=(
            ("equipment_id", "ID"),
            ("name", "Name"),
            ("type", "Type"),
            ("resource_type_id", "Resource Type"),
            ("condition", "Condition"),
        ),
        form_fields=(
            FieldSpec("name", "Name", required=True),
            FieldSpec("equipment_id", "Equipment ID"),
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
        id_column="aircraft_record",
        sort_column="aircraft_id",
        display_columns=(
            ("aircraft_id", "Tail Number"),
            ("type", "Type"),
            ("callsign", "Callsign"),
            ("status", "Status"),
        ),
        form_fields=(
            FieldSpec("aircraft_id", "Tail Number", required=True),
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


def _name_from_master(entity_type: str, master: dict[str, Any], record_id: Any) -> str:
    if entity_type == "personnel":
        return master.get("name") or str(record_id)
    if entity_type == "vehicle":
        return (
            master.get("callsign")
            or master.get("license_plate")
            or " ".join(str(v) for v in [master.get("year"), master.get("make"), master.get("model")] if v)
            or str(record_id)
        )
    if entity_type == "aircraft":
        return master.get("callsign") or master.get("tail_number") or master.get("aircraft_id") or str(record_id)
    if entity_type == "equipment":
        return master.get("name") or master.get("serial_number") or str(record_id)
    return str(record_id)


class CheckInService:
    """API-backed facade that manages master and incident resource check-in."""

    def _has_active_org_assignment(self, person_record: int) -> bool:
        incident_id = _incident_id()
        if not incident_id or not person_record:
            return False
        try:
            rows = _client().get(
                f"/api/incidents/{incident_id}/org/assignments/by-person/{person_record}",
                params={"active_only": True},
            ) or []
        except Exception:
            return False
        return bool(rows)

    def _is_on_incident_team(self, resource_type: str, record_id: Any) -> bool:
        incident_id = _incident_id()
        resource_id = str(record_id or "").strip()
        if not incident_id or not resource_id:
            return False
        field_map = {
            "personnel": "members_json",
            "vehicle": "vehicles_json",
            "aircraft": "aircraft_json",
            "equipment": "equipment_json",
        }
        team_field = field_map.get(resource_type)
        if not team_field:
            return False
        try:
            teams = _client().get(f"/api/incidents/{incident_id}/operations/teams") or []
        except Exception:
            return False
        for team in teams:
            raw_members = team.get(team_field) or []
            if isinstance(raw_members, str):
                try:
                    raw_members = json.loads(raw_members)
                except Exception:
                    raw_members = []
            if isinstance(raw_members, list) and resource_id in {str(item) for item in raw_members}:
                return True
        return False

    def default_arrival_status(
        self,
        resource_type: str,
        row: Optional[Dict[str, Any]] = None,
        *,
        record_id: Any = None,
    ) -> str:
        record = row or {}
        if any(record.get(field) not in (None, "", [], {}) for field in ASSIGNED_HINT_FIELDS):
            return "Assigned"
        config = ENTITY_CONFIG.get(resource_type)
        rec_id = record.get(config.id_column) if config else None
        if self._is_on_incident_team(resource_type, rec_id or record_id):
            return "Assigned"
        if resource_type == "personnel":
            prec = int(record.get("person_record") or record_id or 0)
            if prec and self._has_active_org_assignment(prec):
                return "Assigned"
        return "Available"

    def _checked_in_ids(self, entity_type: str) -> set[str]:
        incident_id = _incident_id()
        if not incident_id:
            return set()
        try:
            rows = _client().get(
                f"/api/incidents/{incident_id}/resource-status",
                params={"entity_type": entity_type},
            ) or []
            checked_ids: set[str] = set()
            for row in rows:
                if str(row.get("status") or "").strip() in CHECKED_IN_STATUSES:
                    record_id = row.get("record_id")
                    if record_id is not None:
                        checked_ids.add(str(record_id))
            logger.info(
                "_checked_in_ids entity_type=%s total=%d checked_in=%d",
                entity_type, len(rows), len(checked_ids),
            )
            return checked_ids
        except Exception:
            logger.exception("_checked_in_ids failed entity_type=%s", entity_type)
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
        payload = dict(data)
        if entity_type == "personnel":
            visible_id = str(payload.pop("id", "") or payload.get("person_id") or "").strip()
            if visible_id:
                payload["person_id"] = visible_id

        # Validate required fields
        if config.id_field is not None:
            supplied = payload.get(config.id_column)
            supplied_str = supplied.strip() if isinstance(supplied, str) else str(supplied) if supplied is not None else ""
            if config.id_field.required and not supplied_str:
                raise ValueError(f"{config.id_field.label} is required")

        for field in config.form_fields:
            raw = payload.get(field.name)
            text = raw.strip() if isinstance(raw, str) else raw
            if field.required and not text:
                raise ValueError(f"{field.label} is required")

        try:
            doc = _client().post(base, json=payload)
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
        logger.info(
            "check-in start entity_type=%s incident_id=%s record_id=%s overrides_keys=%s",
            entity_type,
            incident_id,
            record_id,
            sorted((overrides or {}).keys()),
        )

        if entity_type == "personnel":
            # Personnel check-in writes the canonical resource_status row.
            from . import repository as ci_repo
            from .models import CheckInRecord, PersonnelStatus, Location, normalize_checkin_status
            now_iso = datetime.now().astimezone().isoformat(timespec="seconds")
            prec = int(record_id)
            master = None
            try:
                master = _client().get(f"/api/master/personnel/{prec}") or {}
            except Exception:
                master = {}
            default_status = self.default_arrival_status("personnel", master, record_id=prec)
            ci_status = normalize_checkin_status((overrides or {}).get("status") or default_status)
            personnel_status = PersonnelStatus.ASSIGNED if ci_status == "Assigned" else PersonnelStatus.AVAILABLE
            arrival = (overrides or {}).get("arrival_time") or now_iso
            existing = None
            try:
                existing = ci_repo.fetch_checkin(prec)
            except Exception:
                pass
            if existing is None:
                rec = CheckInRecord(
                    person_record=prec,
                    status=ci_status,
                    arrival_time=arrival,
                    location=Location.ICP,
                    incident_callsign=master.get("callsign"),
                    incident_phone=master.get("phone") or master.get("contact"),
                    team_id=master.get("team_id"),
                    role_on_team=master.get("role") or master.get("primary_role"),
                    ci_status=ci_status,
                    personnel_status=personnel_status,
                )
            else:
                existing.status = ci_status
                existing.ci_status = ci_status
                existing.personnel_status = personnel_status
                existing.arrival_time = arrival
                rec = existing
            try:
                ci_repo.save_checkin(rec)
                logger.info(
                    "check-in personnel resource_status saved incident_id=%s person_record=%s status=%s",
                    incident_id, prec, ci_status,
                )
            except Exception:
                logger.exception(
                    "check-in personnel resource_status save failed incident_id=%s person_record=%s",
                    incident_id, prec,
                )
            doc = {**master, "_checked_in": True, "person_record": prec}
            return doc

        # Non-personnel resources: write to resource_status collection.
        master: dict[str, Any] = {}
        try:
            master = _client().get(f"{_MASTER_BASE[entity_type]}/{record_id}") or {}
        except Exception:
            pass

        resource_name = _name_from_master(entity_type, master, record_id)
        arrival_status = self.default_arrival_status(entity_type, master, record_id=record_id)

        # Visible ID for the Resource ID column on the board
        _visible_id_field = {"vehicle": "vehicle_id", "aircraft": "aircraft_id", "equipment": "equipment_id"}
        visible_id = master.get(_visible_id_field.get(entity_type, "")) or None

        rid = int(record_id) if str(record_id).isdigit() else record_id
        payload: dict[str, Any] = {
            "entity_type": entity_type,
            "record_id": rid,
            "resource_id": visible_id or str(record_id),
            "resource_name": resource_name,
            "resource_type": entity_type.title(),
            "status": (overrides or {}).get("status") or arrival_status,
            "changed_by": "Check-In",
        }
        if master.get("location") or (overrides or {}).get("location"):
            payload["location"] = (overrides or {}).get("location") or master.get("location")

        try:
            doc = _client().post(
                f"/api/incidents/{incident_id}/resource-status",
                json=payload,
            )
        except Exception as exc:
            logger.exception(
                "check-in post failed entity_type=%s incident_id=%s record_id=%s",
                entity_type,
                incident_id,
                record_id,
            )
            raise ValueError(str(exc)) from exc

        logger.info(
            "check-in post succeeded entity_type=%s incident_id=%s record_id=%s",
            entity_type, incident_id, record_id,
        )
        doc["_checked_in"] = True
        return doc

    def get_checked_in_record(self, entity_type: str, record_id: Any) -> Optional[Dict[str, Any]]:
        incident_id = _incident_id()
        if not incident_id:
            return None
        try:
            return _client().get(
                f"/api/incidents/{incident_id}/resource-status/by-entity",
                params={"entity_type": entity_type, "record_id": str(record_id)},
            )
        except Exception:
            return None

    # ------------------------------------------------------------------
    # ID search (returns resolver list for ambiguous matches)
    # ------------------------------------------------------------------

    def search_by_id(
        self, entity_type: str, typed_value: str, limit: int = 30
    ) -> tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """Search for a master record by ID/callsign/etc.

        Returns (exact_match, resolver_list):
        - If exactly one match is found, exact_match is that record
          and resolver_list is empty.
        - If multiple matches are found, exact_match is None and
          resolver_list contains the candidates.
        - If no matches are found, both are empty/None.
        """
        config = ENTITY_CONFIG.get(entity_type)
        if not config:
            return None, []

        results = self.search_master_records(entity_type, typed_value, limit=limit)
        if not results:
            return None, []

        exact_values = [
            str(typed_value.strip().lower()),
        ]
        exact_matches = []
        for row in results:
            candidates = [
                str(row.get("person_id") or "").strip().lower(),
                str(row.get("vehicle_id") or "").strip().lower(),
                str(row.get("equipment_id") or "").strip().lower(),
                str(row.get("aircraft_id") or "").strip().lower(),
                str(row.get("callsign") or "").strip().lower(),
                str(row.get("serial_number") or "").strip().lower(),
                str(row.get("license_plate") or "").strip().lower(),
            ]
            if typed_value.strip().lower() in candidates:
                exact_matches.append(row)

        if len(exact_matches) == 1:
            return exact_matches[0], []
        if len(exact_matches) > 1:
            return None, exact_matches
        if len(results) == 1:
            return results[0], []
        return None, results

    # ------------------------------------------------------------------
    # Organization-filtered listing
    # ------------------------------------------------------------------

    def list_by_organization(
        self, entity_type: str, organization: str
    ) -> List[Dict[str, Any]]:
        """List master records filtered by organization/unit."""
        config = ENTITY_CONFIG.get(entity_type)
        if not config:
            return []
        records = self.list_master_records(entity_type)
        if not organization:
            return records
        org_lower = organization.strip().lower()
        filtered = []
        for r in records:
            org_val = str(r.get("organization") or "")
            if org_lower in org_val.lower():
                filtered.append(r)
        return filtered

    # ------------------------------------------------------------------
    # LDW support
    # ------------------------------------------------------------------

    def update_ldw(
        self, person_id: str, ldw_date: Optional[str] = None,
        ldw_notes: Optional[str] = None,
        ldw_updated_by: Optional[str] = None,
    ) -> None:
        """Update LDW fields on an existing check-in record."""
        incident_id = _incident_id()
        if not incident_id:
            return
        try:
            from . import repository as ci_repo
            rec = ci_repo.fetch_checkin(person_id)
            if rec is None:
                return
            now_iso = datetime.now().astimezone().isoformat(timespec="seconds")
            rec.ldw_date = ldw_date
            rec.ldw_notes = ldw_notes
            rec.ldw_updated_at = now_iso
            rec.ldw_updated_by = ldw_updated_by
            ci_repo.save_checkin(rec)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Planning status transitions
    # ------------------------------------------------------------------

    def set_planning_status(self, person_id: str, planning_status: str) -> Optional[Dict[str, Any]]:
        """Set the linear resource-flow status on a resource_status record."""
        incident_id = _incident_id()
        if not incident_id:
            return None
        try:
            doc = _client().get(
                f"/api/incidents/{incident_id}/resource-status/by-entity",
                params={"entity_type": "personnel", "record_id": str(person_id)},
            )
            if not doc:
                return None
            item_id = doc.get("id")
            if not item_id:
                return None
            return _client().patch(
                f"/api/incidents/{incident_id}/resource-status/{item_id}/status",
                json={"status": planning_status, "changed_by": "Planning"},
            )
        except Exception:
            return None

    def transition_to_checked_in(
        self, person_id: str, arrival_time: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Transition a planning-status record to fully checked in."""
        incident_id = _incident_id()
        if not incident_id:
            return None
        now = arrival_time or datetime.now().astimezone().isoformat(timespec="seconds")
        existing = None
        try:
            from . import repository as ci_repo
            existing = ci_repo.fetch_checkin(person_id)
        except Exception:
            existing = None
        status = self.default_arrival_status(
            "personnel",
            {
                "id": person_id,
                "team_id": getattr(existing, "team_id", None) if existing else None,
                "role_on_team": getattr(existing, "role_on_team", None) if existing else None,
            },
            record_id=person_id,
        )
        if existing is None:
            try:
                logger.info(
                    "transition_to_checked_in creating incident record person_id=%s incident_id=%s arrival_time=%s",
                    person_id,
                    incident_id,
                    now,
                )
                created = self.check_in(
                    "personnel",
                    person_id,
                    overrides={
                        "status": status,
                        "arrival_time": now,
                        "updated_at": now,
                    },
                )
                logger.info(
                    "transition_to_checked_in created incident record person_id=%s incident_id=%s result_keys=%s",
                    person_id,
                    incident_id,
                    sorted(created.keys()) if isinstance(created, dict) else None,
                )
                return created
            except Exception:
                logger.exception(
                    "transition_to_checked_in create fallback failed person_id=%s incident_id=%s",
                    person_id,
                    incident_id,
                )
                return None
        try:
            rs_doc = _client().get(
                f"/api/incidents/{incident_id}/resource-status/by-entity",
                params={"entity_type": "personnel", "record_id": str(person_id)},
            )
            item_id = (rs_doc or {}).get("id")
            if not item_id:
                raise ValueError("No resource_status doc found for person")
            result = _client().patch(
                f"/api/incidents/{incident_id}/resource-status/{item_id}/status",
                json={"status": status, "changed_by": "Check-In Transition"},
            )
            logger.info(
                "transition_to_checked_in patched resource_status person_id=%s incident_id=%s status=%s",
                person_id, incident_id, status,
            )
        except Exception:
            logger.exception(
                "transition_to_checked_in patch failed person_id=%s incident_id=%s",
                person_id,
                incident_id,
            )
            return None

        return result

    # ------------------------------------------------------------------
    # Team check-in / disband
    # ------------------------------------------------------------------

    def team_check_in(
        self,
        team_id: str,
        keep_together: bool = True,
        checked_in_by: Optional[str] = None,
        checkin_notes: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Check in a team. If keep_together=False, also disband."""
        incident_id = _incident_id()
        if not incident_id:
            return None
        try:
            team_doc = _client().get(f"/api/incidents/{incident_id}/operations/teams/{team_id}") or {}
        except Exception:
            team_doc = {}
        status = "Assigned" if any(team_doc.get(field) not in (None, "", [], {}) for field in ("current_task_id", "operational_unit_id", "assignment")) else "Available"
        try:
            return _client().post(
                f"/api/incidents/{incident_id}/checkin/teams/{team_id}/checkin",
                json={
                    "keep_together": keep_together,
                    "checked_in_by": checked_in_by,
                    "checkin_notes": checkin_notes,
                    "status": status,
                },
            )
        except Exception:
            return None

    def team_disband(
        self, team_id: str, disbanded_by: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Disband a team."""
        incident_id = _incident_id()
        if not incident_id:
            return None
        try:
            return _client().post(
                f"/api/incidents/{incident_id}/checkin/teams/{team_id}/disband",
                json={"disbanded_by": disbanded_by},
            )
        except Exception:
            return None

    def list_unchecked_teams(self) -> List[Dict[str, Any]]:
        """List teams that are not checked in (for planning views)."""
        incident_id = _incident_id()
        if not incident_id:
            return []
        try:
            return _client().get(
                f"/api/incidents/{incident_id}/checkin/teams/checked-state",
                params={"checked_in": False, "include_disbanded": False},
            ) or []
        except Exception:
            return []

    def list_planning_status_resources(self, status: str = "") -> List[Dict[str, Any]]:
        """List check-in records in planning statuses."""
        incident_id = _incident_id()
        if not incident_id:
            return []
        try:
            params = {}
            if status:
                params["status"] = status
            return _client().get(
                f"/api/incidents/{incident_id}/checkin/planning-statuses",
                params=params,
            ) or []
        except Exception:
            return []


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
