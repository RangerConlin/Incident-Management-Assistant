"""Data helpers for EMS agency catalogue management.

Talks to the shared API server (``/api/master/ems-agencies...``) rather than
MongoDB directly — see ``utils/api_client.py``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from utils.api_client import APIError, api_client

EMS_AGENCY_TYPES: tuple[str, ...] = (
    "Ground Ambulance",
    "Air Ambulance",
    "Other",
)

_BASE = "/api/master/ems-agencies"


@dataclass
class DuplicateGroup:
    """Grouping of potential duplicate agencies."""

    candidate_ids: List[int]
    reason: str


def _validate_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Client-side mirror of the server's required-field checks.

    Catches obviously-bad input before a round trip; the server re-validates
    regardless, so this only affects how quickly the dialog can show an error.
    """
    data: Dict[str, Any] = {}
    name = (payload.get("name") or "").strip()
    if not name:
        raise ValueError("Name is required")
    data["name"] = name

    type_value = (payload.get("type") or "").strip()
    if type_value not in EMS_AGENCY_TYPES:
        raise ValueError("Type is required")
    data["type"] = type_value

    for field in ("phone", "radio_channel", "address", "city", "state", "zip", "notes"):
        data[field] = (payload.get(field) or "").strip() or None

    for field in ("lat", "lon"):
        raw = payload.get(field)
        if raw in (None, ""):
            data[field] = None
            continue
        try:
            data[field] = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field.upper()} must be a number") from exc

    data["default_on_206"] = bool(payload.get("default_on_206"))
    if "is_active" in payload and payload["is_active"] is not None:
        data["is_active"] = bool(payload["is_active"])
    return data


class EMSAgencyRepository:
    """Client-side facade over the EMS agency catalogue API endpoints."""

    def list_agencies(
        self,
        *,
        search: str | None = None,
        include_inactive: bool = True,
        sort_key: str = "name",
        sort_order: str = "asc",
    ) -> list[dict[str, Any]]:
        rows = api_client.get(
            _BASE, params={"search": search or "", "include_inactive": include_inactive}
        ) or []
        allowed_sort = {"name", "type", "updated_at", "city"}
        sort_field = sort_key if sort_key in allowed_sort else "name"
        reverse = sort_order.lower() == "desc"
        return sorted(rows, key=lambda row: (row.get(sort_field) or "", row.get("name") or ""), reverse=reverse)

    def list_by_ids(self, ids: Iterable[int]) -> list[dict[str, Any]]:
        values = sorted({int(i) for i in ids})
        if not values:
            return []
        rows = api_client.get(_BASE, params={"ids": ",".join(str(v) for v in values)}) or []
        return sorted(rows, key=lambda row: row.get("name") or "")

    def get(self, agency_id: int) -> dict[str, Any] | None:
        try:
            return api_client.get(f"{_BASE}/{int(agency_id)}")
        except APIError as exc:
            if exc.status_code == 404:
                return None
            raise

    def create(self, payload: Mapping[str, Any]) -> int:
        data = _validate_payload(payload)
        try:
            created = api_client.post(_BASE, json=data)
        except APIError as exc:
            if exc.status_code == 422:
                raise ValueError(str(exc)) from exc
            raise
        return int(created["id"])

    def update(self, agency_id: int, payload: Mapping[str, Any]) -> None:
        data = _validate_payload(payload)
        try:
            api_client.patch(f"{_BASE}/{int(agency_id)}", json=data)
        except APIError as exc:
            if exc.status_code == 422:
                raise ValueError(str(exc)) from exc
            raise

    def set_active(self, agency_id: int, active: bool) -> None:
        api_client.post(f"{_BASE}/{int(agency_id)}/active", json={"active": bool(active)})

    def merge(self, survivor_id: int, duplicate_ids: Iterable[int]) -> None:
        dupes = sorted({int(i) for i in duplicate_ids if int(i) != int(survivor_id)})
        if not dupes:
            return
        api_client.post(f"{_BASE}/merge", json={"survivor_id": int(survivor_id), "duplicate_ids": dupes})

    def duplicate_groups(self) -> list[tuple[DuplicateGroup, list[dict[str, Any]]]]:
        groups = api_client.get(f"{_BASE}/duplicates") or []
        return [
            (DuplicateGroup(list(group["candidate_ids"]), group["reason"]), list(group["members"]))
            for group in groups
        ]

    def list_audit_entries(
        self,
        *,
        limit: int = 250,
        start: str | None = None,
        end: str | None = None,
        user_filter: str | None = None,
        action_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if user_filter:
            params["user"] = user_filter
        if action_filter:
            params["action"] = action_filter
        return api_client.get(f"{_BASE}/audit-log", params=params) or []


def map_agencies_to_sections(rows: Sequence[Mapping[str, Any]]) -> Dict[str, List[Mapping[str, Any]]]:
    """Partition EMS agencies (ground/air ambulance services) into ICS-206 sections.

    Hospitals are managed separately via the Hospital Manager and are not part
    of this catalogue.
    """
    sections: Dict[str, List[Mapping[str, Any]]] = {
        "Ambulance Services / Air Ambulance": [],
        "Other": [],
    }
    for row in rows:
        r_type = str(row.get("type") or "").strip()
        # "Ambulance" is accepted for backward compatibility with records
        # created before the type was renamed to "Ground Ambulance".
        if r_type in {"Ground Ambulance", "Ambulance", "Air Ambulance"}:
            key = "Ambulance Services / Air Ambulance"
        else:
            key = "Other"
        sections[key].append(dict(row))
    return sections


def import_to_ics206(
    repository: EMSAgencyRepository,
    agency_ids: Iterable[int],
    *,
    mode: str = "append",
) -> Dict[str, int]:
    """Resolve selected agencies into their ICS-206 destination sections."""
    rows = repository.list_by_ids(agency_ids)
    sections = map_agencies_to_sections(rows)
    summary = {name: len(items) for name, items in sections.items() if items}
    return summary


__all__ = [
    "EMS_AGENCY_TYPES",
    "DuplicateGroup",
    "EMSAgencyRepository",
    "map_agencies_to_sections",
    "import_to_ics206",
]
