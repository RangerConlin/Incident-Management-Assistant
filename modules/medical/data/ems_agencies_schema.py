"""Data helpers for EMS agency catalogue management."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import re
from itertools import combinations
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence

from .mongo_access import get_master_db, strip_mongo_id

logger = logging.getLogger(__name__)

EMS_AGENCY_TYPES: tuple[str, ...] = (
    "Ambulance",
    "Hospital",
    "Air Ambulance",
    "Medical Aid",
    "Other",
)

_TABLE_FIELDS = (
    "name",
    "type",
    "phone",
    "radio_channel",
    "address",
    "city",
    "state",
    "zip",
    "lat",
    "lon",
    "notes",
    "default_on_206",
    "is_active",
    "updated_at",
    "created_at",
)

_NAME_SANITISE_RE = re.compile(r"[^A-Z0-9]+")
_PHONE_SANITISE_RE = re.compile(r"\D+")


def normalize_name(value: str | None) -> str:
    """Return an upper-case identifier with punctuation removed."""
    if not value:
        return ""
    value = value.upper().strip()
    return _NAME_SANITISE_RE.sub("", value)


def normalize_phone(value: str | None) -> str:
    """Return digits-only phone token used to match duplicates."""
    if not value:
        return ""
    return _PHONE_SANITISE_RE.sub("", value)


def sanitize_phone(value: str) -> str:
    """Collapse whitespace and ensure separators are consistent."""
    cleaned = value.replace(";", "/").replace(",", "/")
    cleaned = re.sub(r"\s*[/]\s*", " / ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


@dataclass
class DuplicateGroup:
    """Grouping of potential duplicate agencies."""

    candidate_ids: List[int]
    reason: str


def ensure_schema(conn_factory: Any = None, db: Any = None) -> None:
    """Create MongoDB indexes for EMS agencies.

    The ``conn_factory`` argument is retained for compatibility with older
    callers that passed a connection factory.
    """
    col = (db if db is not None else get_master_db())["ems_agencies"]
    col.create_index([("id", 1)], unique=True)
    col.create_index([("name", 1)])
    col.create_index([("type", 1)])
    col.create_index([("phone", 1)])
    col.create_index([("is_active", 1)])


class EMSAgencyRepository:
    """Persistence layer handling CRUD and reporting for EMS agencies."""

    def __init__(self, conn_factory: Any = None, db: Any = None) -> None:
        self._db = db if db is not None else get_master_db()
        self._col = self._db["ems_agencies"]
        ensure_schema(conn_factory, db=self._db)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _next_id(self) -> int:
        row = self._col.find_one(sort=[("id", -1)], projection={"id": 1})
        return int(row["id"]) + 1 if row and row.get("id") is not None else 1

    def _row(self, document: Mapping[str, Any] | None) -> dict[str, Any] | None:
        row = strip_mongo_id(dict(document)) if document else None
        if not row:
            return None
        row["id"] = int(row["id"])
        row["default_on_206"] = 1 if row.get("default_on_206") else 0
        row["is_active"] = 1 if row.get("is_active", True) else 0
        return row

    def _write_audit(self, action: str, detail: Mapping[str, Any]) -> None:
        try:
            self._db["audit_logs"].insert_one(
                {
                    "ts_utc": self._now(),
                    "action": action,
                    "detail": dict(detail),
                    "entity_type": "ems_agency",
                    "entity_id": detail.get("id") or detail.get("survivor"),
                }
            )
        except Exception:  # pragma: no cover - audit failures should not block CRUD
            logger.exception("Failed to write audit entry for %s", action)

    def list_agencies(
        self,
        *,
        search: str | None = None,
        include_inactive: bool = True,
        sort_key: str = "name",
        sort_order: str = "asc",
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"deleted": {"$ne": True}}
        if not include_inactive:
            query["is_active"] = {"$ne": False}
        if search:
            query["$or"] = [
                {"name": {"$regex": re.escape(search), "$options": "i"}},
                {"type": {"$regex": re.escape(search), "$options": "i"}},
                {"phone": {"$regex": re.escape(search), "$options": "i"}},
                {"radio_channel": {"$regex": re.escape(search), "$options": "i"}},
                {"city": {"$regex": re.escape(search), "$options": "i"}},
                {"state": {"$regex": re.escape(search), "$options": "i"}},
            ]
        allowed_sort = {"name", "type", "updated_at", "city"}
        sort_field = sort_key if sort_key in allowed_sort else "name"
        direction = -1 if sort_order.lower() == "desc" else 1
        rows = [self._row(row) for row in self._col.find(query).sort([(sort_field, direction), ("name", 1)])]
        return [row for row in rows if row is not None]

    def list_by_ids(self, ids: Iterable[int]) -> list[dict[str, Any]]:
        values = sorted({int(i) for i in ids})
        if not values:
            return []
        rows = [self._row(row) for row in self._col.find({"id": {"$in": values}, "deleted": {"$ne": True}}).sort("name", 1)]
        return [row for row in rows if row is not None]

    def get(self, agency_id: int) -> dict[str, Any] | None:
        return self._row(self._col.find_one({"id": int(agency_id), "deleted": {"$ne": True}}))

    def create(self, payload: Mapping[str, Any]) -> int:
        data = self._prepare_payload(payload, creating=True)
        now = self._now()
        new_id = self._next_id()
        data.setdefault("created_at", now)
        data.setdefault("updated_at", now)
        data["id"] = new_id
        data["deleted"] = False
        self._col.insert_one(data)
        self._write_audit("ems_agency.create", {"id": new_id, "action": "create", "data": data})
        return new_id

    def update(self, agency_id: int, payload: Mapping[str, Any]) -> None:
        existing = self.get(int(agency_id))
        if not existing:
            raise ValueError(f"Agency {agency_id} not found")
        data = self._prepare_payload(payload, creating=False)
        changes: MutableMapping[str, Any] = {}
        updates: dict[str, Any] = {}
        for key, value in data.items():
            if existing.get(key) != value:
                updates[key] = value
                changes[key] = {"old": existing.get(key), "new": value}
        if not updates:
            return
        updates["updated_at"] = self._now()
        self._col.update_one({"id": int(agency_id)}, {"$set": updates})
        self._write_audit("ems_agency.update", {"id": int(agency_id), "action": "update", "changes": changes})

    def set_active(self, agency_id: int, active: bool) -> None:
        existing = self.get(int(agency_id))
        if not existing:
            raise ValueError(f"Agency {agency_id} not found")
        if bool(existing.get("is_active")) == bool(active):
            return
        self._col.update_one(
            {"id": int(agency_id)},
            {"$set": {"is_active": bool(active), "updated_at": self._now()}},
        )
        self._write_audit(
            "ems_agency.restore" if active else "ems_agency.deactivate",
            {"id": int(agency_id), "previous": bool(existing.get("is_active")), "active": bool(active)},
        )

    def merge(self, survivor_id: int, duplicate_ids: Iterable[int]) -> None:
        survivor_id = int(survivor_id)
        dupes = {int(i) for i in duplicate_ids if int(i) != survivor_id}
        if not dupes:
            return
        self._col.update_many(
            {"id": {"$in": sorted(dupes)}},
            {"$set": {"is_active": False, "updated_at": self._now()}},
        )
        self._write_audit("ems_agency.merge", {"survivor": survivor_id, "merged": sorted(dupes)})

    def duplicate_groups(self) -> list[tuple[DuplicateGroup, list[dict[str, Any]]]]:
        rows = self.list_agencies(include_inactive=True)
        by_id = {int(row["id"]): row for row in rows if row.get("id") is not None}
        groups: list[set[int]] = []

        phone_groups: dict[str, set[int]] = {}
        for row in rows:
            phone_key = normalize_phone(row.get("phone"))
            if len(phone_key) >= 7:
                phone_groups.setdefault(phone_key, set()).add(int(row["id"]))
        for ids in phone_groups.values():
            if len(ids) > 1:
                _merge_group(groups, ids)

        from difflib import SequenceMatcher

        for a, b in combinations(by_id.values(), 2):
            name_a = normalize_name(a.get("name"))
            name_b = normalize_name(b.get("name"))
            if not name_a or not name_b:
                continue
            if name_a == name_b or SequenceMatcher(None, name_a, name_b).ratio() >= 0.9:
                _merge_group(groups, {int(a["id"]), int(b["id"])})

        result: list[tuple[DuplicateGroup, list[dict[str, Any]]]] = []
        for ids in groups:
            members = [by_id[i] for i in sorted(ids)]
            reason = "Shared phone" if any(
                len(normalize_phone(m.get("phone"))) >= 7
                and normalize_phone(m.get("phone")) == normalize_phone(members[0].get("phone"))
                for m in members
            ) else "Similar name"
            result.append((DuplicateGroup(sorted(ids), reason), members))
        return result

    def list_audit_entries(
        self,
        *,
        limit: int = 250,
        start: str | None = None,
        end: str | None = None,
        user_filter: str | None = None,
        action_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"action": {"$regex": r"^ems_agency\."}}
        if start or end:
            query["ts_utc"] = {}
            if start:
                query["ts_utc"]["$gte"] = start
            if end:
                query["ts_utc"]["$lte"] = end
        if action_filter:
            query["action"] = action_filter
        if user_filter:
            query["user_id"] = {"$regex": re.escape(user_filter), "$options": "i"}
        rows = self._db["audit_logs"].find(query).sort("ts_utc", -1).limit(int(limit))
        return [strip_mongo_id(row) or {} for row in rows]

    def _prepare_payload(self, payload: Mapping[str, Any], *, creating: bool) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        name = (payload.get("name") or "").strip()
        if not name:
            raise ValueError("Name is required")
        data["name"] = name

        type_value = (payload.get("type") or "").strip()
        if type_value not in EMS_AGENCY_TYPES:
            raise ValueError("Type is required")
        data["type"] = type_value

        phone = payload.get("phone") or ""
        data["phone"] = sanitize_phone(phone) if phone else None

        for field in ("radio_channel", "address", "city", "state", "zip", "notes"):
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
        is_active = payload.get("is_active")
        if creating:
            data["is_active"] = is_active in (None, "", True, 1)
        elif is_active is not None:
            data["is_active"] = bool(is_active)
        return {key: value for key, value in data.items() if key in _TABLE_FIELDS}


def _merge_group(groups: list[set[int]], new_ids: set[int]) -> None:
    merged = set(new_ids)
    keep: list[set[int]] = []
    for existing in groups:
        if existing & merged:
            merged |= existing
        else:
            keep.append(existing)
    keep.append(merged)
    groups[:] = keep


def map_agencies_to_sections(rows: Sequence[Mapping[str, Any]]) -> Dict[str, List[Mapping[str, Any]]]:
    """Partition agencies into ICS-206 sections."""
    sections: Dict[str, List[Mapping[str, Any]]] = {
        "Ambulance Services / Air Ambulance": [],
        "Hospitals": [],
        "Medical Aid Stations": [],
        "Other": [],
    }
    for row in rows:
        r_type = str(row.get("type") or "").strip()
        if r_type in {"Ambulance", "Air Ambulance"}:
            key = "Ambulance Services / Air Ambulance"
        elif r_type == "Hospital":
            key = "Hospitals"
        elif r_type == "Medical Aid":
            key = "Medical Aid Stations"
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
    logger.info("[ems] Requested ICS-206 import (mode=%s): %s", mode, summary)
    return summary


__all__ = [
    "EMS_AGENCY_TYPES",
    "DuplicateGroup",
    "EMSAgencyRepository",
    "ensure_schema",
    "normalize_name",
    "normalize_phone",
    "sanitize_phone",
    "map_agencies_to_sections",
    "import_to_ics206",
]
