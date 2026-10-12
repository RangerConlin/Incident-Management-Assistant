"""Public Information router backed by per-incident MongoDB collections."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


RECORD_COLLECTIONS = {
    "pio_media_log": IncidentCollections.PIO_MEDIA_LOG,
    "pio_misinformation_items": IncidentCollections.PIO_MISINFORMATION_ITEMS,
    "pio_talking_points": IncidentCollections.PIO_TALKING_POINTS,
    "pio_distribution_log": IncidentCollections.PIO_DISTRIBUTION_LOG,
    "pio_generated_documents": IncidentCollections.PIO_GENERATED_DOCUMENTS,
}

ORDER_FIELDS = {
    "id",
    "updated_at",
    "created_at",
    "published_at",
    "time",
    "last_update",
    "distributed_at",
    "template_name",
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _next_id(col) -> int:
    doc = col.find_one({}, {"id": 1}, sort=[("id", -1)])
    return int((doc or {}).get("id") or 0) + 1


def _collection_for_table(table: str) -> str:
    try:
        return RECORD_COLLECTIONS[table]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown Public Information table: {table}") from exc


def _sort_from_order(order_by: str) -> list[tuple[str, int]]:
    parts = [part.strip() for part in (order_by or "id DESC").split(",") if part.strip()]
    sort: list[tuple[str, int]] = []
    for part in parts:
        tokens = part.split()
        field = tokens[0]
        if field not in ORDER_FIELDS:
            continue
        direction = -1 if len(tokens) > 1 and tokens[1].upper() == "DESC" else 1
        sort.append((field, direction))
    return sort or [("id", -1)]


def _message_collection(incident_id: str):
    return get_incident_db(incident_id)[IncidentCollections.PIO_MESSAGES]


class PioMessageRepository(BaseRepository):
    collection_name = IncidentCollections.PIO_MESSAGES


class PioMisinformationRepository(BaseRepository):
    collection_name = IncidentCollections.PIO_MISINFORMATION_ITEMS


def _message_repo(incident_id: str) -> PioMessageRepository:
    return PioMessageRepository(get_incident_db(incident_id))


def _misinformation_repo(incident_id: str) -> PioMisinformationRepository:
    return PioMisinformationRepository(get_incident_db(incident_id))


def _next_embedded_approval_id(message: Dict[str, Any]) -> int:
    ids = []
    for approval in message.get("approvals") or []:
        try:
            ids.append(int(approval.get("id") or 0))
        except (TypeError, ValueError):
            continue
    return (max(ids) if ids else 0) + 1


def _next_embedded_timeline_id(item: Dict[str, Any]) -> int:
    ids = []
    for event in item.get("timeline") or []:
        try:
            ids.append(int(event.get("id") or 0))
        except (TypeError, ValueError):
            continue
    return (max(ids) if ids else 0) + 1


@router.get("/incidents/{incident_id}/public-information/messages")
def list_messages(incident_id: str):
    docs = _message_collection(incident_id).find(
        {"incident_id": incident_id, "deleted": {"$ne": True}},
        {"_id": 0},
    ).sort([("updated_at", -1), ("id", -1)])
    return list(docs)


@router.get("/incidents/{incident_id}/public-information/messages/{message_id}")
def get_message(incident_id: str, message_id: int):
    doc = _message_collection(incident_id).find_one(
        {"incident_id": incident_id, "id": int(message_id), "deleted": {"$ne": True}},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Message not found")
    return doc


@router.post("/incidents/{incident_id}/public-information/messages", status_code=201)
def save_message(incident_id: str, payload: Dict[str, Any] = Body(...)):
    col = _message_collection(incident_id)
    now = _utcnow()
    values = dict(payload)
    message_id = values.get("id")
    values["updated_at"] = now
    values.setdefault("created_at", now)
    values.setdefault("related_incident_id", incident_id)
    values.setdefault("incident_id", incident_id)
    values.setdefault("published_at", "")
    values.setdefault("published_by", "")
    values.setdefault("approved_by", "")
    values.setdefault("approved_at", "")
    values.setdefault("archived_by", "")
    values.setdefault("archived_at", "")
    values.setdefault("boilerplate", "")
    values.setdefault("deleted", False)
    user = str(values.pop("_revision_user", "") or "")

    if message_id:
        message_id = int(message_id)
        col.update_one(
            {"incident_id": incident_id, "id": message_id},
            {"$set": values},
            upsert=False,
        )
    else:
        message_id = _next_id(col)
        values["id"] = message_id
        values["_id"] = str(uuid.uuid4())
        values.setdefault("approvals", [])
        col.insert_one(values)

    _add_revision(incident_id, message_id, values, user)
    saved = col.find_one({"incident_id": incident_id, "id": message_id}, {"_id": 0})
    return saved or {}


def _add_revision(incident_id: str, message_id: int, data: Dict[str, Any], user: str = "") -> None:
    col = get_incident_db(incident_id)[IncidentCollections.PIO_MESSAGE_REVISIONS]
    count = col.count_documents({"incident_id": incident_id, "message_id": int(message_id)})
    col.insert_one(
        {
            "_id": str(uuid.uuid4()),
            "id": _next_id(col),
            "incident_id": incident_id,
            "message_id": int(message_id),
            "title": data.get("title", ""),
            "body": data.get("body", ""),
            "template_id": data.get("template_id"),
            "revision_number": count + 1,
            "created_at": _utcnow(),
            "created_by": user,
        }
    )


@router.post("/incidents/{incident_id}/public-information/messages/{message_id}/status")
def set_message_status(incident_id: str, message_id: int, payload: Dict[str, Any] = Body(...)):
    repo = _message_repo(incident_id)
    col = _message_collection(incident_id)
    existing = repo.find_one({"incident_id": incident_id, "id": int(message_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Message not found")
    status = str(payload.get("status") or existing.get("status") or "")
    user = str(payload.get("user") or "")
    now = _utcnow()
    update = {
        "status": status,
        "updated_at": now,
        "published_at": now if status == "Published" else existing.get("published_at", ""),
        "published_by": user if status == "Published" else existing.get("published_by", ""),
        "approved_by": user if status == "Approved" else existing.get("approved_by", ""),
        "approved_at": now if status == "Approved" else existing.get("approved_at", ""),
        "archived_by": user if status == "Archived" else existing.get("archived_by", ""),
        "archived_at": now if status == "Archived" else existing.get("archived_at", ""),
    }
    approval = {
        "id": _next_embedded_approval_id(existing),
        "incident_id": incident_id,
        "message_id": int(message_id),
        "reviewer_id": user,
        "reviewer_name": user,
        "action": status,
        "comment": payload.get("comment", ""),
        "timestamp": now,
    }
    repo.apply_update(
        existing["_id"],
        {
            "$set": update,
            "$push": {"approvals": approval},
        },
    )
    return col.find_one({"incident_id": incident_id, "id": int(message_id)}, {"_id": 0}) or {}


@router.get("/incidents/{incident_id}/public-information/messages/{message_id}/approvals")
def list_approvals(incident_id: str, message_id: int):
    message = _message_repo(incident_id).find_one({"incident_id": incident_id, "id": int(message_id)})
    if not message:
        return []
    return sorted(
        [dict(approval) for approval in message.get("approvals") or []],
        key=lambda approval: approval.get("timestamp") or "",
    )


@router.get("/incidents/{incident_id}/public-information/templates")
def list_templates(incident_id: str, active_only: bool = False):
    query: Dict[str, Any] = {"incident_id": incident_id, "deleted": {"$ne": True}}
    if active_only:
        query["is_active"] = 1
    col = get_incident_db(incident_id)[IncidentCollections.PIO_TEMPLATES]
    return list(col.find(query, {"_id": 0}).sort("template_name", 1))


@router.get("/incidents/{incident_id}/public-information/templates/{template_id}")
def get_template(incident_id: str, template_id: int):
    col = get_incident_db(incident_id)[IncidentCollections.PIO_TEMPLATES]
    doc = col.find_one({"incident_id": incident_id, "id": int(template_id), "deleted": {"$ne": True}}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Template not found")
    return doc


@router.post("/incidents/{incident_id}/public-information/templates", status_code=201)
def save_template(incident_id: str, payload: Dict[str, Any] = Body(...)):
    col = get_incident_db(incident_id)[IncidentCollections.PIO_TEMPLATES]
    now = _utcnow()
    values = dict(payload)
    template_id = values.get("id")
    values["updated_at"] = now
    values.setdefault("created_at", now)
    values.setdefault("incident_id", incident_id)
    values.setdefault("is_active", 1)
    values.setdefault("version", 1)
    values.setdefault("deleted", False)
    if template_id:
        template_id = int(template_id)
        col.update_one({"incident_id": incident_id, "id": template_id}, {"$set": values})
    else:
        template_id = _next_id(col)
        values["id"] = template_id
        values["_id"] = str(uuid.uuid4())
        col.insert_one(values)
    return col.find_one({"incident_id": incident_id, "id": template_id}, {"_id": 0}) or {}


@router.get("/incidents/{incident_id}/public-information/records/{table}")
def list_records(incident_id: str, table: str, order_by: str = "id DESC"):
    col = get_incident_db(incident_id)[_collection_for_table(table)]
    cursor = col.find({"incident_id": incident_id, "deleted": {"$ne": True}}, {"_id": 0}).sort(_sort_from_order(order_by))
    return list(cursor)


@router.post("/incidents/{incident_id}/public-information/records/{table}", status_code=201)
def save_record(incident_id: str, table: str, payload: Dict[str, Any] = Body(...)):
    col = get_incident_db(incident_id)[_collection_for_table(table)]
    values = dict(payload)
    record_id = values.get("id")
    values.setdefault("incident_id", incident_id)
    values.setdefault("deleted", False)
    if table == "pio_misinformation_items":
        values.setdefault("timeline", [])
    if record_id:
        record_id = int(record_id)
        col.update_one({"incident_id": incident_id, "id": record_id}, {"$set": values})
    else:
        record_id = _next_id(col)
        values["id"] = record_id
        values["_id"] = str(uuid.uuid4())
        col.insert_one(values)
    return col.find_one({"incident_id": incident_id, "id": record_id}, {"_id": 0}) or {}


@router.post("/incidents/{incident_id}/public-information/media/{media_id}/response-draft", status_code=201)
def create_response_draft_from_media(incident_id: str, media_id: int, payload: Dict[str, Any] = Body(default={})):
    media_col = get_incident_db(incident_id)[IncidentCollections.PIO_MEDIA_LOG]
    media = media_col.find_one({"incident_id": incident_id, "id": int(media_id), "deleted": {"$ne": True}}, {"_id": 0})
    if not media:
        raise HTTPException(status_code=404, detail="Media inquiry not found")
    user = str(payload.get("user") or "")
    message = save_message(
        incident_id,
        {
            "title": media.get("topic", ""),
            "type": "Holding Statement",
            "audience": "Media",
            "priority": "Normal",
            "status": "Draft",
            "created_by": user,
            "source_media_log_id": int(media_id),
            "related_incident_id": incident_id,
            "_revision_user": user,
        },
    )
    media_col.update_one(
        {"incident_id": incident_id, "id": int(media_id)},
        {"$set": {"related_message_id": message.get("id")}},
    )
    return message


@router.post("/incidents/{incident_id}/public-information/misinformation/{item_id}/timeline", status_code=201)
def add_misinformation_timeline(incident_id: str, item_id: int, payload: Dict[str, Any] = Body(...)):
    repo = _misinformation_repo(incident_id)
    item = repo.find_one({"incident_id": incident_id, "id": int(item_id)})
    if not item:
        raise HTTPException(status_code=404, detail="Misinformation item not found")
    now = _utcnow()
    event = {
        "id": _next_embedded_timeline_id(item),
        "incident_id": incident_id,
        "item_id": int(item_id),
        "event_time": now,
        "event_text": payload.get("event_text", ""),
        "created_by": payload.get("user", ""),
    }
    repo.apply_update(
        item["_id"],
        {
            "$push": {"timeline": event},
            "$set": {"last_update": now},
        },
    )
    return event


@router.get("/incidents/{incident_id}/public-information/misinformation/{item_id}/timeline")
def list_misinformation_timeline(incident_id: str, item_id: int):
    item = _misinformation_repo(incident_id).find_one({"incident_id": incident_id, "id": int(item_id)})
    if not item:
        return []
    return sorted(
        [dict(event) for event in item.get("timeline") or []],
        key=lambda event: event.get("event_time") or "",
    )


@router.get("/incidents/{incident_id}/public-information/summary")
def summary_counts(incident_id: str):
    db = get_incident_db(incident_id)
    messages = db[IncidentCollections.PIO_MESSAGES]
    media = db[IncidentCollections.PIO_MEDIA_LOG]
    misinformation = db[IncidentCollections.PIO_MISINFORMATION_ITEMS]
    base = {"incident_id": incident_id, "deleted": {"$ne": True}}
    return {
        "Pending Approvals": messages.count_documents({**base, "status": "Pending Approval"}),
        "Draft Messages": messages.count_documents({**base, "status": "Draft"}),
        "Published / Released Messages": messages.count_documents({**base, "status": "Published"}),
        "Media Follow-Ups": media.count_documents({**base, "$or": [{"follow_up_needed": 1}, {"follow_up_needed": True}, {"status": "Follow-Up Needed"}]}),
        "Active Misinformation Items": misinformation.count_documents({**base, "status": {"$nin": ["Corrected", "Closed"]}}),
        "Next Briefing / Next Update": "Not scheduled",
    }
