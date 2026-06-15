from __future__ import annotations

from typing import Any

from .models import ApprovalInstance, ApprovalRecord


class ApprovalRepository:
    def __init__(self, incident_id: str):
        self.incident_id = incident_id
        self._base = f"/api/incidents/{incident_id}/approvals"

    def _get(self, path: str, **params):
        from utils.api_client import api_client
        return api_client.get(self._base + path, params=params if params else None)

    def _post(self, path: str, body: dict):
        from utils.api_client import api_client
        return api_client.post(self._base + path, json=body)

    def _put(self, path: str, body: dict):
        from utils.api_client import api_client
        return api_client.put(self._base + path, json=body)

    # ------------------------------------------------------------------
    # Instances

    def get_instance(self, entity_type: str, entity_id: str) -> ApprovalInstance | None:
        try:
            doc = self._get(f"/instances/{entity_type}/{entity_id}")
            return ApprovalInstance.from_dict(doc)
        except Exception:
            return None

    def save_instance(self, instance: ApprovalInstance) -> None:
        self._put(
            f"/instances/{instance.entity_type}/{instance.entity_id}",
            instance.to_dict(),
        )

    def pending_for_roles(self, roles: list[str], personnel_id: str) -> list[dict[str, Any]]:
        return self._post("/pending", {"roles": roles, "personnel_id": personnel_id})

    # ------------------------------------------------------------------
    # Records

    def save_record(self, record: ApprovalRecord) -> None:
        self._post("/records", {
            "entity_type": record.entity_type,
            "entity_id": record.entity_id,
            "step_id": record.step_id,
            "actor_id": record.actor_id,
            "role_at_time": record.role_at_time,
            "assignment_type_at_time": record.assignment_type_at_time,
            "action": record.action,
            "timestamp": record.timestamp,
            "notes": record.notes,
        })

    def get_records(self, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
        return self._get("/records", entity_type=entity_type, entity_id=entity_id)
