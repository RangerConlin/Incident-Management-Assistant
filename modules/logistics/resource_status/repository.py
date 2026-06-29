"""API-backed repository for the Logistics resource status board."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Iterable, Optional

from .models import ResourceAuditEntry, ResourceItem

DERIVED_CHECKED_IN_STATUSES = {
    "Available",
    "Assigned",
    "Out of Service",
    "Preparing for Demobilization",
    "Checked In",
}


class ResourceStatusRepository:
    """Persist and query resource status board rows via the SARApp API server."""

    def _incident_id(self) -> str:
        from utils import incident_context
        from utils.state import AppState
        iid = incident_context.get_active_incident_id() or AppState.get_active_incident()
        if not iid:
            raise RuntimeError("No active incident for resource status board")
        return str(iid)

    def list_resources(self) -> list[ResourceItem]:
        from utils.api_client import api_client
        iid = self._incident_id()
        rows = api_client.get(f"/api/incidents/{iid}/logistics/resource-status")
        return [ResourceItem.from_row(r) for r in rows]

    def get_resource(self, resource_status_id: str) -> Optional[ResourceItem]:
        from utils.api_client import api_client, APIError
        iid = self._incident_id()
        try:
            row = api_client.get(f"/api/incidents/{iid}/logistics/resource-status/{resource_status_id}")
            return ResourceItem.from_row(row)
        except APIError:
            return None

    def get_by_source(self, source_entity_type: str, source_record_id: str) -> Optional[ResourceItem]:
        from utils.api_client import api_client, APIError
        iid = self._incident_id()
        try:
            row = api_client.get(
                f"/api/incidents/{iid}/logistics/resource-status/{source_record_id}/by-source",
                params={"source_entity_type": source_entity_type, "source_record_id": source_record_id},
            )
            return ResourceItem.from_row(row) if row else None
        except (APIError, Exception):
            return None

    def save_resource(self, item: ResourceItem) -> ResourceItem:
        from utils.api_client import api_client, APIError
        iid = self._incident_id()
        payload = item.to_row()
        try:
            api_client.get(f"/api/incidents/{iid}/logistics/resource-status/{item.id}")
            api_client.patch(f"/api/incidents/{iid}/logistics/resource-status/{item.id}", json=payload)
        except APIError:
            api_client.post(f"/api/incidents/{iid}/logistics/resource-status", json=payload)
        return item

    def save_audit_entries(self, entries: Iterable[ResourceAuditEntry]) -> None:
        from utils.api_client import api_client
        entries_list = list(entries)
        if not entries_list:
            return
        by_item: dict[str, list[dict]] = {}
        for entry in entries_list:
            by_item.setdefault(entry.resource_status_id, []).append(entry.to_row())
        iid = self._incident_id()
        for resource_status_id, rows in by_item.items():
            try:
                api_client.post(
                    f"/api/incidents/{iid}/logistics/resource-status/{resource_status_id}/audit",
                    json=rows,
                )
            except Exception:
                pass

    def list_audit_entries(self, resource_status_id: str, limit: int = 50) -> list[dict[str, Any]]:
        from utils.api_client import api_client, APIError
        iid = self._incident_id()
        try:
            return api_client.get(
                f"/api/incidents/{iid}/logistics/resource-status/{resource_status_id}/audit",
                params={"limit": limit},
            )
        except APIError:
            return []

    def source_rows(self) -> list[dict[str, Any]]:
        """Build incident-scoped source rows from team composition and master assets.

        Team-linked assets inherit the team's current status until they are
        physically checked in, which keeps the resource board aligned with the
        team's planning state without implying an actual arrival/check-in.
        """

        from utils.api_client import api_client
        iid = self._incident_id()
        try:
            teams = api_client.get(f"/api/incidents/{iid}/operations/teams") or []
        except Exception:
            return []

        rows: list[dict[str, Any]] = []
        for team in teams:
            team_status = str(team.get("status") or team.get("ci_status") or "Available").strip() or "Available"
            team_name = team.get("name") or f"Team {team.get('int_id') or team.get('team_id')}"
            team_id = team.get("int_id") or team.get("team_id")
            for entity_type, key, collection in (
                ("personnel", "members_json", "personnel"),
                ("vehicle", "vehicles_json", "vehicles"),
                ("aircraft", "aircraft_json", "aircraft"),
                ("equipment", "equipment_json", "equipment"),
            ):
                raw_ids = team.get(key) or []
                if isinstance(raw_ids, str):
                    try:
                        import json
                        raw_ids = json.loads(raw_ids)
                    except Exception:
                        raw_ids = []
                if not isinstance(raw_ids, list):
                    continue
                for ref_id in raw_ids:
                    source_record_id = str(ref_id)
                    if not source_record_id:
                        continue
                    record = self._lookup_master_record(entity_type, source_record_id)
                    if not record:
                        continue
                    rows.append({
                        "entity_type": entity_type,
                        "identifier_column": "id",
                        "record": {
                            **record,
                            "team_id": team_id,
                            "team_name": team_name,
                            "team_status": team_status,
                            "status": team_status,
                            "checked_in": team_status in DERIVED_CHECKED_IN_STATUSES,
                        },
                    })
        return rows

    def _lookup_master_record(self, entity_type: str, source_record_id: str) -> dict[str, Any] | None:
        from utils.api_client import api_client, APIError
        try:
            if entity_type == "personnel":
                return api_client.get(f"/api/master/personnel/{source_record_id}")
            if entity_type == "vehicle":
                return api_client.get(f"/api/master/vehicles/{source_record_id}")
            if entity_type == "aircraft":
                return api_client.get(f"/api/master/aircraft/{source_record_id}")
            if entity_type == "equipment":
                return api_client.get(f"/api/master/equipment/{source_record_id}")
        except APIError:
            return None
        except Exception:
            return None
        return None

    def ensure_schema(self, conn=None) -> None:
        pass


def new_identifier() -> str:
    return uuid.uuid4().hex


def now_local_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
