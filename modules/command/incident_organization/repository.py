from __future__ import annotations

"""SQLite repository for incident organization management."""

import json
import os
from datetime import datetime, timezone
from typing import Iterable, Sequence

from .models import (
    ACTIVE_ASSIGNMENT_TYPES,
    AssignmentHistoryEntry,
    GeneratedFormSnapshot,
    OrganizationPosition,
    OrganizationTemplate,
    PositionAssignment,
    POSITION_STATUSES,
)


def _data_dir() -> Path:
    return Path(os.environ.get("CHECKIN_DATA_DIR", "data"))


def _incident_db_path(incident_id: str) -> Path:
    safe_id = str(incident_id).strip().replace("/", "-")
    if not safe_id:
        raise ValueError("incident identifier must not be empty")
    base = _data_dir() / "incidents"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{safe_id}.db"


def get_incident_connection(incident_id: str) -> sqlite3.Connection:
    conn = sqlite3.connect(_incident_db_path(incident_id))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _qualification_text(values: Sequence[str] | str | None) -> str:
    if values is None:
        return "[]"
    if isinstance(values, str):
        values = [v.strip() for v in values.split(",") if v.strip()]
    return json.dumps(list(values))


def _qualification_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return [part.strip() for part in value.split(",") if part.strip()]
    return [str(item) for item in parsed if str(item).strip()]


DEFAULT_FEMA_NIMS_TEMPLATE_NAME = "FEMA/NIMS Basic ICS Structure"


def _default_organization_templates() -> list[OrganizationTemplate]:
    """Return built-in organization templates available to every incident."""

    payload: list[dict[str, object]] = [
        {
            "key": "incident_command",
            "title": "Incident Command",
            "classification": "command",
            "sort_order": 0,
            "notes": "Top-level NIMS incident command organization.",
        },
        {
            "key": "incident_commander",
            "parent_key": "incident_command",
            "title": "Incident Commander",
            "classification": "position",
            "is_critical": True,
            "sort_order": 0,
            "required_qualifications": ["Incident Commander per AHJ/NIMS"],
        },
        {
            "key": "deputy_incident_commander",
            "parent_key": "incident_command",
            "title": "Deputy Incident Commander",
            "classification": "position",
            "sort_order": 1,
        },
        {
            "key": "command_staff",
            "parent_key": "incident_command",
            "title": "Command Staff",
            "classification": "unit",
            "sort_order": 2,
        },
        {
            "key": "safety_officer",
            "parent_key": "command_staff",
            "title": "Safety Officer",
            "classification": "position",
            "is_critical": True,
            "sort_order": 0,
            "required_qualifications": ["Safety Officer per AHJ/NIMS"],
        },
        {
            "key": "public_information_officer",
            "parent_key": "command_staff",
            "title": "Public Information Officer",
            "classification": "position",
            "sort_order": 1,
        },
        {
            "key": "liaison_officer",
            "parent_key": "command_staff",
            "title": "Liaison Officer",
            "classification": "position",
            "sort_order": 2,
        },
        {
            "key": "agency_representative",
            "parent_key": "command_staff",
            "title": "Agency Representative",
            "classification": "position",
            "sort_order": 3,
        },
        {
            "key": "operations_section",
            "parent_key": "incident_command",
            "title": "Operations Section",
            "classification": "section",
            "sort_order": 3,
        },
        {
            "key": "operations_section_chief",
            "parent_key": "operations_section",
            "title": "Operations Section Chief",
            "classification": "position",
            "is_critical": True,
            "sort_order": 0,
            "required_qualifications": ["Operations Section Chief per AHJ/NIMS"],
        },
        {
            "key": "branch_director",
            "parent_key": "operations_section",
            "title": "Branch Director",
            "classification": "position",
            "sort_order": 1,
        },
        {
            "key": "division_group_supervisor",
            "parent_key": "operations_section",
            "title": "Division/Group Supervisor",
            "classification": "position",
            "sort_order": 2,
        },
        {
            "key": "staging_area_manager",
            "parent_key": "operations_section",
            "title": "Staging Area Manager",
            "classification": "position",
            "sort_order": 3,
        },
        {
            "key": "planning_section",
            "parent_key": "incident_command",
            "title": "Planning Section",
            "classification": "section",
            "sort_order": 4,
        },
        {
            "key": "planning_section_chief",
            "parent_key": "planning_section",
            "title": "Planning Section Chief",
            "classification": "position",
            "is_critical": True,
            "sort_order": 0,
            "required_qualifications": ["Planning Section Chief per AHJ/NIMS"],
        },
        {
            "key": "resources_unit_leader",
            "parent_key": "planning_section",
            "title": "Resources Unit Leader",
            "classification": "position",
            "sort_order": 1,
        },
        {
            "key": "situation_unit_leader",
            "parent_key": "planning_section",
            "title": "Situation Unit Leader",
            "classification": "position",
            "sort_order": 2,
        },
        {
            "key": "documentation_unit_leader",
            "parent_key": "planning_section",
            "title": "Documentation Unit Leader",
            "classification": "position",
            "sort_order": 3,
        },
        {
            "key": "demobilization_unit_leader",
            "parent_key": "planning_section",
            "title": "Demobilization Unit Leader",
            "classification": "position",
            "sort_order": 4,
        },
        {
            "key": "technical_specialist",
            "parent_key": "planning_section",
            "title": "Technical Specialist",
            "classification": "position",
            "sort_order": 5,
        },
        {
            "key": "logistics_section",
            "parent_key": "incident_command",
            "title": "Logistics Section",
            "classification": "section",
            "sort_order": 5,
        },
        {
            "key": "logistics_section_chief",
            "parent_key": "logistics_section",
            "title": "Logistics Section Chief",
            "classification": "position",
            "is_critical": True,
            "sort_order": 0,
            "required_qualifications": ["Logistics Section Chief per AHJ/NIMS"],
        },
        {
            "key": "service_branch",
            "parent_key": "logistics_section",
            "title": "Service Branch",
            "classification": "branch",
            "sort_order": 1,
        },
        {
            "key": "service_branch_director",
            "parent_key": "service_branch",
            "title": "Service Branch Director",
            "classification": "position",
            "sort_order": 0,
        },
        {
            "key": "communications_unit_leader",
            "parent_key": "service_branch",
            "title": "Communications Unit Leader",
            "classification": "position",
            "sort_order": 1,
        },
        {
            "key": "medical_unit_leader",
            "parent_key": "service_branch",
            "title": "Medical Unit Leader",
            "classification": "position",
            "sort_order": 2,
        },
        {
            "key": "food_unit_leader",
            "parent_key": "service_branch",
            "title": "Food Unit Leader",
            "classification": "position",
            "sort_order": 3,
        },
        {
            "key": "support_branch",
            "parent_key": "logistics_section",
            "title": "Support Branch",
            "classification": "branch",
            "sort_order": 2,
        },
        {
            "key": "support_branch_director",
            "parent_key": "support_branch",
            "title": "Support Branch Director",
            "classification": "position",
            "sort_order": 0,
        },
        {
            "key": "supply_unit_leader",
            "parent_key": "support_branch",
            "title": "Supply Unit Leader",
            "classification": "position",
            "sort_order": 1,
        },
        {
            "key": "facilities_unit_leader",
            "parent_key": "support_branch",
            "title": "Facilities Unit Leader",
            "classification": "position",
            "sort_order": 2,
        },
        {
            "key": "ground_support_unit_leader",
            "parent_key": "support_branch",
            "title": "Ground Support Unit Leader",
            "classification": "position",
            "sort_order": 3,
        },
        {
            "key": "finance_admin_section",
            "parent_key": "incident_command",
            "title": "Finance/Admin Section",
            "classification": "section",
            "sort_order": 6,
        },
        {
            "key": "finance_admin_section_chief",
            "parent_key": "finance_admin_section",
            "title": "Finance/Admin Section Chief",
            "classification": "position",
            "is_critical": True,
            "sort_order": 0,
            "required_qualifications": ["Finance/Admin Section Chief per AHJ/NIMS"],
        },
        {
            "key": "time_unit_leader",
            "parent_key": "finance_admin_section",
            "title": "Time Unit Leader",
            "classification": "position",
            "sort_order": 1,
        },
        {
            "key": "procurement_unit_leader",
            "parent_key": "finance_admin_section",
            "title": "Procurement Unit Leader",
            "classification": "position",
            "sort_order": 2,
        },
        {
            "key": "compensation_claims_unit_leader",
            "parent_key": "finance_admin_section",
            "title": "Compensation/Claims Unit Leader",
            "classification": "position",
            "sort_order": 3,
        },
        {
            "key": "cost_unit_leader",
            "parent_key": "finance_admin_section",
            "title": "Cost Unit Leader",
            "classification": "position",
            "sort_order": 4,
        },
    ]
    return [
        OrganizationTemplate(
            id=None,
            incident_id=None,
            name=DEFAULT_FEMA_NIMS_TEMPLATE_NAME,
            description=(
                "A starter FEMA/NIMS ICS organization with command staff, "
                "general staff sections, logistics branches, and common unit leaders."
            ),
            payload=payload,
        )
    ]


def _template_text(value: object) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _template_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


class ApiIncidentOrganizationRepository:
    """MongoDB-backed implementation via the SARApp API server."""

    def __init__(self, incident_id: str):
        self.incident_id = str(incident_id)
        self._base = f"/api/incidents/{self.incident_id}/org"

    def _get(self, path: str, **params):
        from utils.api_client import api_client
        return api_client.get(self._base + path, params=params if params else None)

    def _post(self, path: str, body):
        from utils.api_client import api_client
        return api_client.post(self._base + path, json=body)

    def _patch(self, path: str, body=None, **params):
        from utils.api_client import api_client
        return api_client.patch(self._base + path, json=body, params=params if params else None)

    def _put(self, path: str, body):
        from utils.api_client import api_client
        return api_client.put(self._base + path, json=body)

    def _delete(self, path: str):
        from utils.api_client import api_client
        return api_client.delete(self._base + path)

    # ------------------------------------------------------------------

    def ensure_schema(self) -> None:
        pass  # MongoDB is schemaless

    def upsert_position(self, position: OrganizationPosition) -> int:
        body = {
            "position_id": position.id,
            "title": position.title,
            "classification": position.classification,
            "parent_position_id": position.parent_position_id,
            "operational_period": position.operational_period,
            "required_qualifications": list(position.required_qualifications),
            "is_critical": position.is_critical,
            "is_custom": position.is_custom,
            "status": position.status,
            "sort_order": position.sort_order,
            "notes": position.notes,
        }
        result = self._post("/positions", body)
        return int(result["position_id"])

    def list_positions(self, include_inactive: bool = False) -> list[OrganizationPosition]:
        docs = self._get("/positions", include_inactive=str(include_inactive).lower())
        return [self._doc_to_position(d) for d in docs]

    def get_position(self, position_id: int) -> OrganizationPosition | None:
        try:
            doc = self._get(f"/positions/{position_id}")
            return self._doc_to_position(doc)
        except Exception:
            return None

    def move_position(self, position_id: int, parent_position_id: int | None) -> None:
        self._patch(f"/positions/{position_id}/move", {"parent_position_id": parent_position_id})

    def list_operational_units(
        self, classifications: set[str] | None = None
    ) -> list[OrganizationPosition]:
        from utils.api_client import api_client
        params: dict = {}
        if classifications:
            params["classifications"] = ",".join(classifications)
        docs = api_client.get(self._base + "/units", params=params if params else None)
        return [self._doc_to_position(d) for d in docs]

    def deactivate_position(self, position_id: int) -> None:
        self._delete(f"/positions/{position_id}")

    def list_templates(self) -> list[OrganizationTemplate]:
        docs = self._get("/templates")
        return [self._doc_to_template(d) for d in docs]

    def get_template_by_name(self, name: str) -> OrganizationTemplate | None:
        try:
            from utils.api_client import api_client
            doc = api_client.get(self._base + "/templates/by-name", params={"name": name})
            return self._doc_to_template(doc)
        except Exception:
            return None

    def save_template(self, template: OrganizationTemplate) -> int:
        body = {
            "template_id": template.id,
            "name": template.name,
            "description": template.description,
            "payload": template.payload,
        }
        result = self._post("/templates", body)
        return int(result["template_id"])

    def apply_template_payload(self, payload: Sequence[dict[str, object]]) -> list[int]:
        result = self._post("/templates/apply", {"payload": list(payload)})
        return [int(pid) for pid in result]

    def add_assignment(self, assignment: PositionAssignment) -> int:
        body = {
            "position_id": assignment.position_id,
            "personnel_id": assignment.personnel_id,
            "display_name": assignment.display_name,
            "assignment_type": assignment.assignment_type,
            "start_time": assignment.start_time,
            "end_time": assignment.end_time,
            "operational_period": assignment.operational_period,
            "assigned_by": assignment.assigned_by,
            "notes": assignment.notes,
        }
        result = self._post("/assignments", body)
        return int(result["assignment_id"])

    def end_assignment(
        self,
        assignment_id: int,
        *,
        end_time: str | None = None,
        changed_by: str | None = None,
        notes: str | None = None,
    ) -> None:
        self._patch(
            f"/assignments/{assignment_id}/end",
            {"end_time": end_time, "changed_by": changed_by, "notes": notes},
        )

    def list_assignments(
        self, position_id: int | None = None, *, active_only: bool = True
    ) -> list[PositionAssignment]:
        from utils.api_client import api_client
        params: dict = {"active_only": str(active_only).lower()}
        if position_id is not None:
            params["position_id"] = position_id
        docs = api_client.get(self._base + "/assignments", params=params)
        return [self._doc_to_assignment(d) for d in docs]

    def list_assignment_history(
        self, position_id: int | None = None
    ) -> list[AssignmentHistoryEntry]:
        from utils.api_client import api_client
        params: dict = {}
        if position_id is not None:
            params["position_id"] = position_id
        docs = api_client.get(self._base + "/history", params=params if params else None)
        return [self._doc_to_history(d) for d in docs]

    def replace_requirements(self, position_id: int, qualifications: Iterable[str]) -> None:
        self._put(f"/positions/{position_id}/requirements", {"qualifications": list(qualifications)})

    def save_generated_snapshot(self, snapshot: GeneratedFormSnapshot) -> int:
        body = {
            "form_type": snapshot.form_type,
            "generated_at": snapshot.generated_at,
            "operational_period": snapshot.operational_period,
            "source_version": snapshot.source_version,
            "payload": snapshot.payload,
        }
        result = self._post("/snapshots", body)
        return int(result["snapshot_id"])

    # ------------------------------------------------------------------

    @staticmethod
    def _doc_to_position(doc: dict) -> OrganizationPosition:
        return OrganizationPosition(
            id=doc.get("id") or doc.get("position_id"),
            incident_id=doc.get("incident_id", ""),
            title=doc.get("title", ""),
            classification=doc.get("classification", "position"),
            parent_position_id=doc.get("parent_position_id"),
            operational_period=doc.get("operational_period"),
            required_qualifications=list(doc.get("required_qualifications") or []),
            is_critical=bool(doc.get("is_critical", False)),
            is_custom=bool(doc.get("is_custom", False)),
            status=doc.get("status", "active"),
            sort_order=int(doc.get("sort_order", 0) or 0),
            notes=doc.get("notes"),
        )

    @staticmethod
    def _doc_to_template(doc: dict) -> OrganizationTemplate:
        return OrganizationTemplate(
            id=doc.get("id") or doc.get("template_id"),
            incident_id=doc.get("incident_id"),
            name=doc.get("name", ""),
            description=doc.get("description"),
            payload=list(doc.get("payload") or []),
        )

    @staticmethod
    def _doc_to_assignment(doc: dict) -> PositionAssignment:
        return PositionAssignment(
            id=doc.get("id") or doc.get("assignment_id"),
            incident_id=doc.get("incident_id", ""),
            position_id=int(doc.get("position_id", 0)),
            personnel_id=doc.get("personnel_id"),
            display_name=doc.get("display_name", ""),
            assignment_type=doc.get("assignment_type", "primary"),
            start_time=doc.get("start_time"),
            end_time=doc.get("end_time"),
            operational_period=doc.get("operational_period"),
            assigned_by=doc.get("assigned_by"),
            notes=doc.get("notes"),
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
        )

    @staticmethod
    def _doc_to_history(doc: dict) -> AssignmentHistoryEntry:
        return AssignmentHistoryEntry(
            id=doc.get("id") or doc.get("history_id"),
            incident_id=doc.get("incident_id", ""),
            assignment_id=doc.get("assignment_id"),
            position_id=int(doc.get("position_id", 0)),
            personnel_id=doc.get("personnel_id"),
            display_name=doc.get("display_name", ""),
            assignment_type=doc.get("assignment_type", "primary"),
            action=doc.get("action", ""),
            effective_time=doc.get("effective_time"),
            operational_period=doc.get("operational_period"),
            changed_by=doc.get("changed_by"),
            notes=doc.get("notes"),
        )
