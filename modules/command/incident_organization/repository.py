from __future__ import annotations

from typing import Any, List, Optional, Sequence

from modules.common.models.ics_positions import get_position

from .models import (
    ACTIVE_ASSIGNMENT_TYPES,
    ASSIGNMENT_TYPE_PRIMARY,
    OrganizationPosition,
    OrganizationTemplate,
    PositionAssignment,
    normalize_assignment_type,
)


def _catalog_title(key: str, fallback: str) -> str:
    position = get_position(key)
    return position.title if position else fallback


def _sort_key(value: Any) -> tuple[bool, Any]:
    """Sort ``None`` last regardless of the other values' type."""
    return (value is None, value if value is not None else "")


def _sorted_by(docs: list[dict], fields: Sequence[str]) -> list[dict]:
    return sorted(docs, key=lambda d: tuple(_sort_key(d.get(f)) for f in fields))


class ApiIncidentOrganizationRepository:
    """MongoDB-backed implementation via the SARApp API server."""

    def __init__(self, incident_id: str):
        self.incident_id = str(incident_id)
        self._base = f"/api/incidents/{self.incident_id}/org"

    def _cached_docs(self, collection: str) -> Optional[list[dict]]:
        """Return cached incident-scoped docs for ``collection``, or None if
        the incident cache isn't loaded for this incident."""
        from utils.incident_cache import incident_cache

        if incident_cache.incident_id != self.incident_id:
            return None
        return incident_cache.get_all(collection)

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
            "sort_order": position.sort_order,
        }
        result = self._post("/positions", body)
        return int(result["position_id"])

    def list_positions(self, include_inactive: bool = False) -> list[OrganizationPosition]:
        cached = self._cached_docs("incident_org")
        if cached is not None:
            docs = _sorted_by(cached, ("parent_position_id", "sort_order", "title"))
        else:
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
        cls_set = classifications or {"branch", "division", "group", "staging_area"}
        cached = self._cached_docs("incident_org")
        if cached is not None:
            filtered = [
                d for d in cached
                if d.get("classification") in cls_set
            ]
            docs = _sorted_by(filtered, ("sort_order", "title"))
        else:
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

    def add_assignment(self, assignment: PositionAssignment) -> str:
        body = {
            "position_id": assignment.position_id,
            "person_record": assignment.person_record,
            "assignment_type": assignment.assignment_type,
            "start_time": assignment.start_time,
            "end_time": assignment.end_time,
        }
        result = self._post("/assignments", body)
        return result["assignment_id"]

    def end_assignment(
        self,
        assignment_id: str | int,
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
        cached = self._cached_docs("incident_org")
        if cached is not None:
            docs = self._assignment_docs_from_positions(cached, self._cached_personnel_names())
            if position_id is not None:
                docs = [d for d in docs if d.get("position_id") == position_id]
            if active_only:
                docs = [d for d in docs if d.get("end_time") is None]
            docs = _sorted_by(docs, ("position_id", "start_time", "assignment_id"))
        else:
            from utils.api_client import api_client
            params: dict = {"active_only": str(active_only).lower()}
            if position_id is not None:
                params["position_id"] = position_id
            docs = api_client.get(self._base + "/assignments", params=params)
        return [self._doc_to_assignment(d) for d in docs]

    def list_assignments_for_person(
        self, person_record: int, *, active_only: bool = True
    ) -> list[PositionAssignment]:
        cached = self._cached_docs("incident_org")
        if cached is not None:
            filtered = [
                d for d in self._assignment_docs_from_positions(cached, self._cached_personnel_names())
                if d.get("person_record") == person_record
            ]
            if active_only:
                filtered = [d for d in filtered if d.get("end_time") is None]
            docs = _sorted_by(filtered, ("position_id", "start_time"))
        else:
            from utils.api_client import api_client
            params: dict = {"active_only": str(active_only).lower()}
            docs = api_client.get(
                self._base + f"/assignments/by-person/{person_record}", params=params
            )
        return [self._doc_to_assignment(d) for d in docs]

    @staticmethod
    def _doc_to_position(doc: dict) -> OrganizationPosition:
        return OrganizationPosition(
            id=doc.get("id") or doc.get("position_id"),
            incident_id=doc.get("incident_id", ""),
            title=doc.get("title", ""),
            classification=doc.get("classification", "position"),
            parent_position_id=doc.get("parent_position_id"),
            operational_period=None,
            required_qualifications=[],
            is_critical=False,
            is_custom=False,
            is_air_ops="air operations" in str(doc.get("title", "")).casefold(),
            status="active",
            sort_order=int(doc.get("sort_order", 0) or 0),
            notes=None,
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
            person_record=int(doc["person_record"]) if doc.get("person_record") is not None else None,
            person_name=doc.get("person_name", ""),
            assignment_type=normalize_assignment_type(
                doc.get("assignment_type", ASSIGNMENT_TYPE_PRIMARY)
            ),
            start_time=doc.get("start_time"),
            end_time=doc.get("end_time"),
            operational_period=doc.get("operational_period"),
            assigned_by=doc.get("assigned_by"),
            notes=doc.get("notes"),
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
        )

    def _cached_personnel_names(self) -> dict[int, str]:
        cached = self._cached_docs("incident_personnel")
        if cached is None:
            return {}
        names: dict[int, str] = {}
        for person in cached:
            try:
                record = int(person.get("person_record"))
            except (TypeError, ValueError):
                continue
            name = str(person.get("name") or "").strip()
            if not name:
                name = " ".join(
                    part
                    for part in (
                        str(person.get("first_name") or "").strip(),
                        str(person.get("last_name") or "").strip(),
                    )
                    if part
                )
            names[record] = name
        return names

    @staticmethod
    def _assignment_docs_from_positions(
        positions: list[dict],
        personnel_names: dict[int, str] | None = None,
    ) -> list[dict]:
        personnel_names = personnel_names or {}
        rows: list[dict] = []
        for position in positions:
            position_id = position.get("position_id")
            if position_id is None:
                continue
            for bucket, assignment_type in (
                ("primary", ASSIGNMENT_TYPE_PRIMARY),
                ("deputies", "deputy"),
                ("staff_assistants", "staff_assistant"),
            ):
                for assignment in position.get(bucket) or []:
                    person_record = assignment.get("person_record")
                    try:
                        record_key = int(person_record)
                    except (TypeError, ValueError):
                        record_key = None
                    atype = (
                        "trainee"
                        if assignment.get("trainee")
                        else assignment_type
                    )
                    rows.append({
                        "assignment_id": f"{position_id}:{bucket}:{person_record}",
                        "incident_id": position.get("incident_id", ""),
                        "position_id": position_id,
                        "person_record": person_record,
                        "person_name": personnel_names.get(record_key, "") if record_key is not None else "",
                        "assignment_type": atype,
                        "start_time": assignment.get("start_time"),
                        "end_time": assignment.get("end_time"),
                    })
        return rows


def _default_organization_templates() -> list[OrganizationTemplate]:
    """Built-in ICS organization templates offered alongside any
    incident-saved custom templates. Referenced by
    data/db/sarapp_db/api/routers/incident_org.py::_builtin_templates().
    """

    basic_payload = [
        {"key": "ic", "title": _catalog_title("incident_commander", "Incident Commander"), "classification": "command", "is_critical": True},
        {"key": "safety", "parent_key": "ic", "title": _catalog_title("safety_officer", "Safety Officer"), "classification": "position"},
        {"key": "pio", "parent_key": "ic", "title": _catalog_title("public_information_officer", "Public Information Officer"), "classification": "position"},
        {"key": "liaison", "parent_key": "ic", "title": _catalog_title("liaison_officer", "Liaison Officer"), "classification": "position"},
        {"key": "ops", "parent_key": "ic", "title": _catalog_title("operations_section_chief", "Operations Section Chief"), "classification": "section"},
        {"key": "planning", "parent_key": "ic", "title": _catalog_title("planning_section_chief", "Planning Section Chief"), "classification": "section"},
        {"key": "logistics", "parent_key": "ic", "title": _catalog_title("logistics_section_chief", "Logistics Section Chief"), "classification": "section"},
        {"key": "finance", "parent_key": "ic", "title": _catalog_title("finance_admin_section_chief", "Finance/Administration Section Chief"), "classification": "section"},
    ]

    expanded_payload = basic_payload + [
        {"key": "staging", "parent_key": "ops", "title": _catalog_title("staging_area_manager", "Staging Area Manager"), "classification": "position"},
        {
            "key": "air_ops_branch", "parent_key": "ops", "title": "Air Operations Branch",
            "classification": "branch", "is_air_ops": True,
        },
        {"key": "resources_unit", "parent_key": "planning", "title": _catalog_title("resources_unit_leader", "Resources Unit Leader"), "classification": "position"},
        {"key": "situation_unit", "parent_key": "planning", "title": _catalog_title("situation_unit_leader", "Situation Unit Leader"), "classification": "position"},
        {"key": "documentation_unit", "parent_key": "planning", "title": _catalog_title("documentation_unit_leader", "Documentation Unit Leader"), "classification": "position"},
        {"key": "demob_unit", "parent_key": "planning", "title": _catalog_title("demobilization_unit_leader", "Demobilization Unit Leader"), "classification": "position"},
        {"key": "time_unit", "parent_key": "finance", "title": _catalog_title("time_unit_leader", "Time Unit Leader"), "classification": "position"},
        {"key": "procurement_unit", "parent_key": "finance", "title": _catalog_title("procurement_unit_leader", "Procurement Unit Leader"), "classification": "position"},
        {"key": "comp_claims_unit", "parent_key": "finance", "title": _catalog_title("compensation_claims_unit_leader", "Compensation/Claims Unit Leader"), "classification": "position"},
        {"key": "cost_unit", "parent_key": "finance", "title": _catalog_title("cost_unit_leader", "Cost Unit Leader"), "classification": "position"},
    ]

    sar_minimal_payload = [
        {"key": "ic", "title": _catalog_title("incident_commander", "Incident Commander"), "classification": "command", "is_critical": True},
        {"key": "safety", "parent_key": "ic", "title": _catalog_title("safety_officer", "Safety Officer"), "classification": "position"},
        {"key": "ops", "parent_key": "ic", "title": _catalog_title("operations_section_chief", "Operations Section Chief"), "classification": "section"},
        {"key": "staging", "parent_key": "ops", "title": _catalog_title("staging_area_manager", "Staging Area Manager"), "classification": "position"},
    ]

    # Civil Air Patrol - every Command Staff role and Section Chief includes
    # a deputy slot. Deputies are set as assignment_type="deputy" on the
    # parent position rather than as separate position nodes (the Unified
    # Assignment Dialog allows selecting "deputy" as the assignment type).
    # Branches (Ground Ops / Air Ops) similarly get their deputy director
    # via a second assignment on the branch position itself.
    cap_payload = [
        {"key": "ic", "title": _catalog_title("incident_commander", "Incident Commander"), "classification": "command", "is_critical": True},

        {"key": "safety", "parent_key": "ic", "title": _catalog_title("safety_officer", "Safety Officer"), "classification": "position"},

        {"key": "liaison", "parent_key": "ic", "title": _catalog_title("liaison_officer", "Liaison Officer"), "classification": "position"},

        {"key": "pio", "parent_key": "ic", "title": _catalog_title("public_information_officer", "Public Information Officer"), "classification": "position"},

        {"key": "planning", "parent_key": "ic", "title": _catalog_title("planning_section_chief", "Planning Section Chief"), "classification": "section"},
        {"key": "situation_unit", "parent_key": "planning", "title": _catalog_title("situation_unit_leader", "Situation Unit Leader"), "classification": "position"},

        {"key": "logistics", "parent_key": "ic", "title": _catalog_title("logistics_section_chief", "Logistics Section Chief"), "classification": "section"},
        {"key": "communications_unit", "parent_key": "logistics", "title": _catalog_title("communications_unit_leader", "Communications Unit Leader"), "classification": "position"},

        {"key": "finance", "parent_key": "ic", "title": _catalog_title("finance_admin_section_chief", "Finance/Administration Section Chief"), "classification": "section"},

        {"key": "intel", "parent_key": "ic", "title": _catalog_title("intelligence_section_chief", "Intelligence Section Chief"), "classification": "section"},

        {"key": "ops", "parent_key": "ic", "title": _catalog_title("operations_section_chief", "Operations Section Chief"), "classification": "section"},
        {"key": "ground_ops_branch", "parent_key": "ops", "title": "Ground Operations Branch", "classification": "branch"},
        {
            "key": "air_ops_branch", "parent_key": "ops", "title": "Air Operations Branch",
            "classification": "branch", "is_air_ops": True,
        },
    ]

    return [
        OrganizationTemplate(
            id=None,
            incident_id=None,
            name="ICS Command & General Staff (Basic)",
            description=(
                "Incident Commander, Command Staff (Safety/PIO/Liaison), and "
                "the four Section Chiefs. Starting point for most incidents - "
                "add branches/units as the incident grows."
            ),
            payload=basic_payload,
        ),
        OrganizationTemplate(
            id=None,
            incident_id=None,
            name="Type 3 Incident (Expanded)",
            description=(
                "Basic structure plus deputies, an Air Operations Branch "
                "(flagged so it correctly populates the dedicated Air Ops "
                "field on ICS 203/207 instead of being counted as a numbered "
                "branch), and the standard Planning/Finance units. Operations "
                "display stays limited to the Operations Section structure."
            ),
            payload=expanded_payload,
        ),
        OrganizationTemplate(
            id=None,
            incident_id=None,
            name="SAR Initial Response (Minimal)",
            description=(
                "Incident Commander, Safety Officer, Operations Section "
                "Chief, and a Staging Area Manager - enough to start tasking "
                "teams on a hasty/initial-response search before the full "
                "organization is staffed."
            ),
            payload=sar_minimal_payload,
        ),
        OrganizationTemplate(
            id=None,
            incident_id=None,
            name="Civil Air Patrol (Standard)",
            description=(
                "Incident Commander, Command Staff (Safety/Liaison/PIO), and "
                "Planning/Logistics/Finance/Intelligence Section Chiefs - "
                "every one of those with a deputy. Planning includes a "
                "Situation Unit Leader (SITL); Logistics includes a "
                "Communications Unit Leader (COML); Intelligence is its own "
                "standalone section, not folded under Planning. Operations "
                "Section Chief (with deputy) splits into a Ground "
                "Operations Branch and an Air Operations Branch (pre-flagged "
                "so it populates the form's dedicated Air Ops field instead "
                "of a numbered branch slot)."
            ),
            payload=cap_payload,
        ),
    ]
