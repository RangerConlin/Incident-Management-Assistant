from __future__ import annotations

from typing import Any, Optional

from .models import ApprovalInstance


class ApprovalRepository:
    """Thin client over the shared approvals workflow API.

    Escalation, step activation/advancement, and who-can-sign checks live
    server-side (`server/sarapp_db/sarapp_db/api/routers/approvals.py`) so
    desktop and web drive the same approval chains through the same
    endpoints instead of each re-deriving that logic locally.
    """

    def __init__(self, incident_id: str):
        self.incident_id = incident_id
        self._base = f"/api/incidents/{incident_id}/approvals"

    def _get(self, path: str, **params):
        from utils.api_client import api_client
        return api_client.get(self._base + path, params=params if params else None)

    def _post(self, path: str, body: dict):
        from utils.api_client import api_client
        return api_client.post(self._base + path, json=body)

    def get_instance(self, entity_type: str, entity_id: str) -> ApprovalInstance | None:
        try:
            doc = self._get(f"/instances/{entity_type}/{entity_id}")
            return ApprovalInstance.from_dict(doc)
        except Exception:
            return None

    def preview_start(self, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
        return self._get(f"/{entity_type}/{entity_id}/start/preview")

    def start(
        self, entity_type: str, entity_id: str, assign_actors: Optional[dict[str, int]] = None
    ) -> ApprovalInstance:
        doc = self._post(f"/{entity_type}/{entity_id}/start", {"assign_actors": assign_actors or {}})
        return ApprovalInstance.from_dict(doc)

    def preview_sign(self, entity_type: str, entity_id: str, step_id: str) -> list[dict[str, Any]]:
        return self._get(f"/{entity_type}/{entity_id}/sign/preview", step_id=step_id)

    def sign(
        self,
        entity_type: str,
        entity_id: str,
        step_id: str,
        actor_id: int,
        action: str,
        notes: Optional[str] = None,
        assign_actors: Optional[dict[str, int]] = None,
    ) -> ApprovalInstance:
        doc = self._post(f"/{entity_type}/{entity_id}/sign", {
            "step_id": step_id,
            "actor_id": actor_id,
            "action": action,
            "notes": notes,
            "assign_actors": assign_actors or {},
        })
        return ApprovalInstance.from_dict(doc)

    def pending_for_person(self, person_record: int) -> list[dict[str, Any]]:
        return self._get(f"/pending/{person_record}")

    def assign_step(
        self, entity_type: str, entity_id: str, step_id: str, actor_id: int
    ) -> ApprovalInstance:
        doc = self._post(f"/{entity_type}/{entity_id}/assign-step", {
            "step_id": step_id,
            "actor_id": actor_id,
        })
        return ApprovalInstance.from_dict(doc)
