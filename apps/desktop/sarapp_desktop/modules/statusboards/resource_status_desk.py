"""Resource Status Desk.

Keeps the resource status board rows current by reading from the active
incident's API-backed Mongo data and refreshing when cache events indicate
the incident changed.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from PySide6.QtCore import QObject, Signal

from utils.incident_cache import incident_cache

logger = logging.getLogger(__name__)

_RESOURCE_STATUS_COLLECTION = "resource_status"
_TEAMS_COLLECTION = "teams"
_INCIDENT_ORG_COLLECTION = "incident_org"

_WATCHED_COLLECTIONS = {
    _RESOURCE_STATUS_COLLECTION,
    _TEAMS_COLLECTION,
    _INCIDENT_ORG_COLLECTION,
}

# Statuses that represent "active" resources — team/org assignment can
# advance these to "Assigned" but the desk never regresses from these.
_ACTIVE_STATUSES = {"Checked In", "Available", "Out of Service"}

# Entity-type → field name holding the record id in master records
_ENTITY_RECORD_FIELD = {
    "vehicle": "vehicle_record",
    "aircraft": "aircraft_record",
    "equipment": "equipment_record",
}

# Team document field → entity type for non-personnel team members
_TEAM_MEMBER_FIELDS = [
    ("member_personnel_ids", "personnel"),
    ("vehicles_json", "vehicle"),
    ("aircraft_json", "aircraft"),
    ("equipment_json", "equipment"),
]


class ResourceStatusDesk(QObject):
    """Emits ``resource_rows_changed`` whenever resource status data changes.

    ``resource_rows_changed`` carries the full current row list — boards
    are expected to re-render from it directly.
    """

    resource_rows_changed = Signal(list)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []
        incident_cache.changed.connect(self._on_cache_changed)
        incident_cache.snapshotLoaded.connect(self._on_snapshot_loaded)
        self._rebuild()

    # ------------------------------------------------------------------
    # Public reads
    # ------------------------------------------------------------------

    def resource_rows(self) -> list[dict[str, Any]]:
        return list(self._rows)

    # ------------------------------------------------------------------
    # Cache reactions
    # ------------------------------------------------------------------

    def _on_snapshot_loaded(self) -> None:
        self._backfill_resource_ids()
        self._sync_team_members()
        self._sync_org_assignments()
        self._rebuild()

    def _on_cache_changed(self, collection: str, op: str, doc_id: str) -> None:
        if collection not in _WATCHED_COLLECTIONS:
            return
        if collection == _TEAMS_COLLECTION:
            self._sync_team_members()
        elif collection == _INCIDENT_ORG_COLLECTION:
            self._sync_org_assignments()
        self._rebuild()

    # ------------------------------------------------------------------
    # Resource ID backfill
    # ------------------------------------------------------------------

    def _backfill_resource_ids(self) -> None:
        """Patch personnel resource_status docs that are missing resource_id.

        Runs once on snapshot load so docs created before the resource_id field
        was added show the public person_id instead of the internal record_id.
        """
        try:
            self._do_backfill_resource_ids()
        except Exception:
            logger.exception("ResourceStatusDesk: resource_id backfill failed")

    def _do_backfill_resource_ids(self) -> None:
        from utils import incident_context
        from utils.api_client import api_client

        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return

        docs = self._fetch_resource_status_docs()
        for doc in docs:
            entity_type = doc.get("entity_type", "")
            record_id = doc.get("record_id")
            if record_id is None:
                continue
            rs_id = str(doc.get("id") or doc.get("_id") or "")
            if not rs_id:
                continue

            visible_id: Optional[str] = None
            try:
                if entity_type == "personnel":
                    master = api_client.get(f"/api/master/personnel/{record_id}")
                    visible_id = (master or {}).get("person_id") or None
                elif entity_type == "vehicle":
                    master = api_client.get(f"/api/master/vehicles/{record_id}")
                    visible_id = (master or {}).get("vehicle_id") or None
                elif entity_type == "aircraft":
                    master = api_client.get(f"/api/master/aircraft/{record_id}")
                    visible_id = (master or {}).get("aircraft_id") or None
                elif entity_type == "equipment":
                    master = api_client.get(f"/api/master/equipment/{record_id}")
                    visible_id = (master or {}).get("equipment_id") or None
            except Exception:
                continue

            if visible_id and str(doc.get("resource_id") or "") != str(visible_id):
                try:
                    api_client.patch(
                        f"/api/incidents/{incident_id}/resource-status/{rs_id}",
                        json={"resource_id": str(visible_id)},
                    )
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Team member sync
    # ------------------------------------------------------------------

    def _sync_team_members(self) -> None:
        """Create resource_status docs for non-personnel team members that
        don't have one yet.

        Personnel docs are created by the check-in service; this method
        handles vehicles, aircraft, and equipment embedded in team documents.
        """
        try:
            self._do_sync_team_members()
        except Exception:
            logger.exception("ResourceStatusDesk: team member sync failed")

    def _do_sync_team_members(self) -> None:
        from utils import incident_context
        from utils.api_client import api_client

        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return

        teams = self._fetch_team_docs()
        existing_docs = self._fetch_resource_status_docs()
        existing_by_key: dict[tuple[str, Any], dict[str, Any]] = {
            (
                d.get("entity_type", ""),
                int(d.get("record_id")) if str(d.get("record_id") or "").isdigit() else d.get("record_id"),
            ): d
            for d in existing_docs
            if d.get("record_id") is not None
        }

        for team in teams:
            team_name = team.get("name") or str(team.get("int_id") or "")
            team_status = str(team.get("status") or "Available").strip()

            for json_field, entity_type in _TEAM_MEMBER_FIELDS:
                raw = team.get(json_field) or []
                if isinstance(raw, str):
                    try:
                        raw = json.loads(raw)
                    except Exception:
                        raw = []
                if not isinstance(raw, list):
                    continue

                for ref_id in raw:
                    if ref_id is None:
                        continue
                    record_id = int(ref_id) if str(ref_id).isdigit() else ref_id
                    key = (entity_type, record_id)

                    # Look up master record for display name and source metadata.
                    master: dict[str, Any] = {}
                    resource_name = str(record_id)
                    source_entity_type = entity_type
                    source_record_id: Any = record_id
                    try:
                        master_ep = {
                            "personnel": f"/api/master/personnel/{record_id}",
                            "vehicle": f"/api/master/vehicles/{record_id}",
                            "aircraft": f"/api/master/aircraft/{record_id}",
                            "equipment": f"/api/master/equipment/{record_id}",
                        }.get(entity_type)
                        if master_ep:
                            master = api_client.get(master_ep)
                            resource_name = (
                                master.get("callsign")
                                or master.get("license_plate")
                                or master.get("name")
                                or master.get("serial_number")
                                or str(record_id)
                            )
                            if entity_type == "personnel":
                                source_record_id = master.get("person_record") or master.get("int_id") or record_id
                                resource_name = master.get("name") or str(record_id)
                    except Exception:
                        pass

                    desired_status = "Assigned" if team_status in _ACTIVE_STATUSES else team_status

                    existing = existing_by_key.get(key)
                    if existing is not None:
                        rs_id = str(existing.get("id") or existing.get("_id") or "")
                        if not rs_id:
                            continue
                        patch: dict[str, Any] = {}
                        if existing.get("assigned_to") != team_name:
                            patch["assigned_to"] = team_name
                        if existing.get("resource_name") != resource_name:
                            patch["resource_name"] = resource_name
                        if existing.get("resource_type") != entity_type.title():
                            patch["resource_type"] = entity_type.title()
                        visible_id = None
                        if entity_type == "personnel":
                            visible_id = master.get("person_id") or source_record_id
                        elif entity_type == "vehicle":
                            visible_id = master.get("vehicle_id") or source_record_id
                        elif entity_type == "aircraft":
                            visible_id = master.get("aircraft_id") or source_record_id
                        elif entity_type == "equipment":
                            visible_id = master.get("equipment_id") or source_record_id
                        if visible_id and str(existing.get("resource_id") or "") != str(visible_id):
                            patch["resource_id"] = str(visible_id)
                        if patch:
                            try:
                                api_client.patch(
                                    f"/api/incidents/{incident_id}/resource-status/{rs_id}",
                                    json=patch,
                                )
                            except Exception:
                                pass

                        current_status = str(existing.get("status") or "").strip()
                        if desired_status == "Assigned" and current_status in _ACTIVE_STATUSES:
                            try:
                                api_client.patch(
                                    f"/api/incidents/{incident_id}/resource-status/{rs_id}/status",
                                    json={"status": "Assigned", "changed_by": "Desk Sync"},
                                )
                            except Exception:
                                pass
                        continue

                    try:
                        payload = {
                            "entity_type": entity_type,
                            "record_id": record_id,
                            "resource_name": resource_name,
                            "resource_type": entity_type.title(),
                            "status": desired_status,
                            "assigned_to": team_name,
                            "changed_by": "Desk Sync",
                        }
                        if entity_type == "personnel":
                            payload["resource_id"] = str(master.get("person_id") or source_record_id)
                        elif entity_type == "vehicle":
                            payload["resource_id"] = str(master.get("vehicle_id") or source_record_id)
                        elif entity_type == "aircraft":
                            payload["resource_id"] = str(master.get("aircraft_id") or source_record_id)
                        elif entity_type == "equipment":
                            payload["resource_id"] = str(master.get("equipment_id") or source_record_id)
                        if entity_type in {"personnel", "vehicle", "aircraft", "equipment"}:
                            payload["source_entity_type"] = source_entity_type
                            payload["source_record_id"] = str(source_record_id)
                        api_client.post(
                            f"/api/incidents/{incident_id}/resource-status",
                            json=payload,
                        )
                        existing_by_key[key] = payload
                    except Exception:
                        pass

    # ------------------------------------------------------------------
    # Org assignments sync (scaffolded)
    # ------------------------------------------------------------------

    def _sync_org_assignments(self) -> None:
        try:
            self._do_sync_org_assignments()
        except Exception:
            logger.exception("ResourceStatusDesk: org assignment sync failed")

    def _do_sync_org_assignments(self) -> None:
        from utils import incident_context
        from utils.api_client import api_client

        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return

        assignments = self._fetch_org_assignments_docs()
        active_assignments = [
            a for a in assignments
            if a.get("end_time") is None and a.get("person_record") is not None
        ]

        # Position id → title from cache
        pos_title: dict[int, str] = {
            p["position_id"]: p.get("title", "")
            for p in self._fetch_org_positions_docs()
            if p.get("position_id") is not None
        }

        # Personnel resource_status docs keyed by record_id
        rs_by_record: dict[Any, dict] = {
            d.get("record_id"): d
            for d in self._fetch_resource_status_docs()
            if d.get("entity_type") == "personnel"
        }

        active_titles_by_person: dict[Any, set[str]] = {}
        for assignment in active_assignments:
            title = pos_title.get(assignment.get("position_id"))
            if title:
                active_titles_by_person.setdefault(assignment.get("person_record"), set()).add(title)

        # Clear stale org assignment references. Team/task assignment can own
        # assigned_to, so only clear assigned_to when it still equals the org
        # title we are removing.
        for person_record, rs_doc in rs_by_record.items():
            current_ref = str(rs_doc.get("assignment_reference") or "")
            if not current_ref:
                continue
            if current_ref in active_titles_by_person.get(person_record, set()):
                continue
            rs_id = str(rs_doc.get("id") or rs_doc.get("_id") or "")
            if not rs_id:
                continue
            patch: dict[str, Any] = {"assignment_reference": None}
            if str(rs_doc.get("assigned_to") or "") == current_ref:
                patch["assigned_to"] = None
            try:
                api_client.patch(
                    f"/api/incidents/{incident_id}/resource-status/{rs_id}",
                    json=patch,
                )
                rs_doc["assignment_reference"] = None
                if "assigned_to" in patch:
                    rs_doc["assigned_to"] = None
            except Exception:
                continue

        for assignment in active_assignments:
            person_record = assignment.get("person_record")
            position_id = assignment.get("position_id")
            title = pos_title.get(position_id) if position_id is not None else None
            if not title:
                continue

            rs_doc = rs_by_record.get(person_record)
            if rs_doc is None:
                continue  # Not checked in — don't create a doc; check-in owns that

            # If assigned_to is already set (team assignment takes priority), store
            # the org position in assignment_reference only
            rs_id = str(rs_doc.get("id") or rs_doc.get("_id") or "")
            if not rs_id:
                continue

            current_assigned_to = rs_doc.get("assigned_to") or ""
            current_ref = rs_doc.get("assignment_reference") or ""

            patch: dict[str, Any] = {}
            if not current_assigned_to:
                patch["assigned_to"] = title
            if current_ref != title:
                patch["assignment_reference"] = title

            if patch:
                try:
                    api_client.patch(
                        f"/api/incidents/{incident_id}/resource-status/{rs_id}",
                        json=patch,
                    )
                except Exception:
                    continue

            # Advance status to Assigned if in an active non-assigned status
            current_status = rs_doc.get("status", "")
            if current_status in _ACTIVE_STATUSES:
                try:
                    api_client.patch(
                        f"/api/incidents/{incident_id}/resource-status/{rs_id}/status",
                        json={"status": "Assigned", "changed_by": "Org Sync"},
                    )
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Rebuild
    # ------------------------------------------------------------------

    def _rebuild(self) -> None:
        try:
            self._backfill_resource_ids()
            docs = self._fetch_resource_status_docs()
            self._rows = [self._doc_to_row(d) for d in docs]
        except Exception:
            logger.exception("ResourceStatusDesk: rebuild failed")
            return
        self.resource_rows_changed.emit(list(self._rows))

    @staticmethod
    def _cached_docs(collection: str) -> Optional[list[dict[str, Any]]]:
        """Return cached docs for ``collection`` if the incident cache is
        loaded for the active incident, else None so callers fall back to
        the API."""
        from utils import incident_context

        incident_id = incident_context.get_active_incident_id()
        if not incident_id or incident_cache.incident_id != str(incident_id):
            return None
        return incident_cache.get_all(collection)

    @staticmethod
    def _fetch_resource_status_docs() -> list[dict[str, Any]]:
        cached = ResourceStatusDesk._cached_docs(_RESOURCE_STATUS_COLLECTION)
        if cached is not None:
            return sorted(cached, key=lambda d: str(d.get("resource_name") or ""))

        from utils import incident_context
        from utils.api_client import api_client

        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return []
        try:
            return api_client.get(f"/api/incidents/{incident_id}/resource-status") or []
        except Exception:
            logger.exception("ResourceStatusDesk: failed to fetch resource_status docs")
            return []

    @staticmethod
    def _fetch_team_docs() -> list[dict[str, Any]]:
        cached = ResourceStatusDesk._cached_docs(_TEAMS_COLLECTION)
        if cached is not None:
            return cached

        from utils import incident_context
        from utils.api_client import api_client

        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return []
        try:
            return api_client.get(f"/api/incidents/{incident_id}/operations/teams") or []
        except Exception:
            logger.exception("ResourceStatusDesk: failed to fetch team docs")
            return []

    @staticmethod
    def _fetch_org_assignments_docs() -> list[dict[str, Any]]:
        cached = ResourceStatusDesk._cached_docs(_INCIDENT_ORG_COLLECTION)
        if cached is not None:
            rows: list[dict[str, Any]] = []
            for position in cached:
                position_id = position.get("position_id")
                for bucket, assignment_type in (
                    ("primary", "primary"),
                    ("deputies", "deputy"),
                    ("staff_assistants", "staff_assistant"),
                ):
                    for assignment in position.get(bucket) or []:
                        rows.append({
                            "position_id": position_id,
                            "person_record": assignment.get("person_record"),
                            "assignment_type": "trainee" if assignment.get("trainee") else assignment_type,
                            "end_time": assignment.get("end_time"),
                        })
            return rows

        from utils import incident_context
        from utils.api_client import api_client

        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return []
        try:
            return api_client.get(
                f"/api/incidents/{incident_id}/org/assignments",
                params={"active_only": "false"},
            ) or []
        except Exception:
            logger.exception("ResourceStatusDesk: failed to fetch org assignments")
            return []

    @staticmethod
    def _fetch_org_positions_docs() -> list[dict[str, Any]]:
        # Mirrors the API's default include_inactive=False (status == "active").
        cached = ResourceStatusDesk._cached_docs(_INCIDENT_ORG_COLLECTION)
        if cached is not None:
            return cached

        from utils import incident_context
        from utils.api_client import api_client

        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return []
        try:
            return api_client.get(f"/api/incidents/{incident_id}/org/positions") or []
        except Exception:
            logger.exception("ResourceStatusDesk: failed to fetch org positions")
            return []

    # ------------------------------------------------------------------
    # Document → row mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _doc_to_row(doc: dict[str, Any]) -> dict[str, Any]:
        """Map a resource_status document to the dict the board renders."""
        d = dict(doc)
        oid = d.pop("_id", None)
        # Expose the MongoDB id as 'id' for item-level operations (edits, etc.)
        if "id" not in d and oid is not None:
            d["id"] = str(oid)
        # Map collection field names → ResourceItem field names
        if "resource_id" not in d or not d["resource_id"]:
            d["resource_id"] = str(d.get("record_id") or "")
        if "source_entity_type" not in d:
            d["source_entity_type"] = d.get("entity_type")
        if "source_record_id" not in d:
            d["source_record_id"] = str(d.get("record_id") or "")
        if not d.get("last_updated"):
            d["last_updated"] = d.get("updated_at")
        return d


_DESK: Optional[ResourceStatusDesk] = None


def get_resource_status_desk() -> ResourceStatusDesk:
    global _DESK
    if _DESK is None:
        _DESK = ResourceStatusDesk()
    return _DESK


__all__ = ["ResourceStatusDesk", "get_resource_status_desk"]
