"""API-backed service for the Logistics Resource Requests module.

Maintains the same interface as the SQLite-backed ResourceRequestService
so UI panels (ResourceRequestListPanel, ResourceRequestDetailPanel) continue
to work without changes.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ..models.enums import ApprovalAction, FulfillmentStatus, Priority, RequestStatus
from . import validators
from .validators import ValidationError

ENTITY_REQUEST = "resource_request"
ENTITY_ITEM = "resource_request_item"
ENTITY_FULFILLMENT = "resource_fulfillment"
ENTITY_APPROVAL = "resource_request_approval"

ACTION_STATUS_MAP = {
    ApprovalAction.SUBMIT: RequestStatus.SUBMITTED,
    ApprovalAction.REVIEW: RequestStatus.REVIEWED,
    ApprovalAction.APPROVE: RequestStatus.APPROVED,
    ApprovalAction.DENY: RequestStatus.DENIED,
    ApprovalAction.CANCEL: RequestStatus.CANCELLED,
    ApprovalAction.REOPEN: RequestStatus.REVIEWED,
}


class ResourceRequestService:
    """API-backed service implementing the resource request lifecycle."""

    def __init__(self, incident_id: str, db_path: Path | None = None):
        self.incident_id = incident_id

    def _client(self):
        from utils.api_client import api_client
        return api_client

    def _base(self) -> str:
        return f"/api/incidents/{self.incident_id}/logistics/resource-requests"

    def _generate_id(self) -> str:
        return uuid.uuid4().hex

    def create_request(self, header: Dict[str, object], items: Iterable[Dict[str, object]]) -> str:
        header = dict(header)
        priority = validators.validate_priority(header["priority"])
        header["priority"] = priority.value
        header.setdefault("status", RequestStatus.DRAFT.value)
        request_id = str(header.get("id") or self._generate_id())
        header["id"] = request_id
        header["items"] = list(items)
        self._client().post(self._base(), json=header)
        return request_id

    def update_request(self, request_id: str, patch: Dict[str, object]) -> None:
        patch = dict(patch)
        if "priority" in patch:
            priority = validators.validate_priority(patch["priority"])
            patch["priority"] = priority.value
        if "status" in patch:
            raise ValidationError("Use change_status to update the workflow status")
        self._client().patch(f"{self._base()}/{request_id}", json=patch)

    def add_items(self, request_id: str, items: Iterable[Dict[str, object]]) -> List[str]:
        result = self._client().post(f"{self._base()}/{request_id}/items", json=list(items))
        return result.get("ids", [])

    def replace_items(self, request_id: str, items: Iterable[Dict[str, object]]) -> None:
        self._client().put(f"{self._base()}/{request_id}/items", json=list(items))

    def change_status(self, request_id: str, status: str, actor_id: str, note: Optional[str] = None) -> None:
        new_status = validators.validate_status(status)
        current = validators.validate_status(self.get_request(request_id)["status"])
        validators.validate_status_transition(current, new_status)
        self._client().post(
            f"{self._base()}/{request_id}/status",
            json={"status": new_status.value, "actor_id": actor_id, "note": note},
        )

    def record_approval(self, request_id: str, action: str, actor_id: str, note: Optional[str] = None) -> str:
        parsed_action = validators.validate_approval_action(action, note)
        result = self._client().post(
            f"{self._base()}/{request_id}/approvals",
            json={"action": parsed_action.value, "actor_id": actor_id, "note": note},
        )
        return result.get("id", "")

    def assign_fulfillment(
        self,
        request_id: str,
        supplier_id: Optional[str] = None,
        team_id: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        destination_location: Optional[str] = None,
        destination_facility_id: Optional[str] = None,
        eta_utc: Optional[str] = None,
        note: Optional[str] = None,
    ) -> str:
        result = self._client().post(
            f"{self._base()}/{request_id}/fulfillments",
            json={
                "supplier_id": supplier_id,
                "team_id": team_id,
                "vehicle_id": vehicle_id,
                "destination_location": destination_location,
                "destination_facility_id": destination_facility_id,
                "eta_utc": eta_utc,
                "note": note,
            },
        )
        return result.get("id", "")

    def update_fulfillment(
        self,
        fulfillment_id: str,
        status: str,
        note: Optional[str] = None,
        eta_utc: Optional[str] = None,
        destination_location: Optional[str] = None,
        destination_facility_id: Optional[str] = None,
        *,
        request_id: Optional[str] = None,
    ) -> None:
        parsed_status = validators.validate_fulfillment_status(status)
        # Only include fields the caller actually provided — the router treats
        # a key's absence from the PATCH body as "leave unchanged", but a
        # present key with a None value as "clear it". Always sending every
        # keyword's default (None) would wipe fields like destination_location
        # on a status-only update.
        payload: Dict[str, object] = {"status": parsed_status.value}
        if note is not None:
            payload["note"] = note
        if eta_utc is not None:
            payload["eta_utc"] = eta_utc
        if destination_location is not None:
            payload["destination_location"] = destination_location
        if destination_facility_id is not None:
            payload["destination_facility_id"] = destination_facility_id
        if request_id:
            self._client().patch(
                f"{self._base()}/{request_id}/fulfillments/{fulfillment_id}",
                json=payload,
            )
            return
        # Fallback: search all requests for the matching fulfillment
        requests = self._client().get(self._base())
        for req in requests:
            rid = req.get("id", "")
            if not rid:
                continue
            detail = self._client().get(f"{self._base()}/{rid}")
            for f in detail.get("fulfillments") or []:
                if f.get("id") == fulfillment_id:
                    self._client().patch(
                        f"{self._base()}/{rid}/fulfillments/{fulfillment_id}",
                        json=payload,
                    )
                    return
        raise ValidationError(f"Unknown fulfillment record: {fulfillment_id}")

    def list_requests(self, filters: Dict[str, object]) -> List[Dict[str, object]]:
        params: dict = {}
        if filters.get("status"):
            s = filters["status"]
            if isinstance(s, str):
                params["status"] = validators.validate_status(s).value
        if filters.get("priority"):
            params["priority"] = validators.validate_priority(filters["priority"]).value
        if filters.get("text"):
            params["text"] = filters["text"]
        return self._client().get(self._base(), params=params)

    def get_request(self, request_id: str) -> Dict[str, object]:
        return self._client().get(f"{self._base()}/{request_id}")

    def list_suppliers(self) -> list:
        return []
