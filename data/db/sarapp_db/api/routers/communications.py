"""Communications router — master radio channels, ICS 205 plan, traffic log."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db
from sarapp_db.mongo.repository import BaseRepository

master_router = APIRouter()
incident_router = APIRouter()


# ---------------------------------------------------------------------------
# Repositories
#
# All collections here are keyed by app-defined string ids (channel_id,
# comms_id, preset_id) rather than `_id`, and none carry a `deleted` field
# with BaseRepository semantics — `deleted` is instead a plain boolean flag
# managed entirely by these handlers (soft-delete-by-convention, not via
# BaseRepository.soft_delete). soft_deletes is therefore disabled everywhere
# so find/count don't inject an extra filter.
# ---------------------------------------------------------------------------

class RadioChannelsRepository(BaseRepository):
    collection_name = MasterCollections.RADIO_CHANNELS
    soft_deletes = False


class IncidentChannelsRepository(BaseRepository):
    collection_name = IncidentCollections.INCIDENT_CHANNELS
    soft_deletes = False


class ICS205InstanceRepository(BaseRepository):
    """One document per incident holding ICS-205 header fields that aren't
    tied to any single channel row (special instructions, which operational
    period the plan is for)."""
    collection_name = IncidentCollections.ICS_205_INSTANCES
    soft_deletes = False


class CommunicationsLogRepository(BaseRepository):
    collection_name = IncidentCollections.COMMUNICATIONS_LOG
    soft_deletes = False


class CommsLogAuditRepository(BaseRepository):
    collection_name = IncidentCollections.COMMS_LOG_AUDIT
    soft_deletes = False


class CommsLogFiltersRepository(BaseRepository):
    collection_name = IncidentCollections.COMMS_LOG_FILTERS
    soft_deletes = False


class TeamsRepository(BaseRepository):
    collection_name = IncidentCollections.TEAMS
    soft_deletes = False


class IncidentPersonnelRepository(BaseRepository):
    collection_name = IncidentCollections.INCIDENT_PERSONNEL
    soft_deletes = False


def _radio_channels_repo() -> RadioChannelsRepository:
    return RadioChannelsRepository(get_master_db())


def _incident_channels_repo(incident_id: str) -> IncidentChannelsRepository:
    return IncidentChannelsRepository(get_incident_db(incident_id))


def _ics205_instance_repo(incident_id: str) -> ICS205InstanceRepository:
    return ICS205InstanceRepository(get_incident_db(incident_id))


def _comms_log_repo(incident_id: str) -> CommunicationsLogRepository:
    return CommunicationsLogRepository(get_incident_db(incident_id))


def _comms_audit_repo(incident_id: str) -> CommsLogAuditRepository:
    return CommsLogAuditRepository(get_incident_db(incident_id))


def _comms_filters_repo(incident_id: str) -> CommsLogFiltersRepository:
    return CommsLogFiltersRepository(get_incident_db(incident_id))


def _teams_repo(incident_id: str) -> TeamsRepository:
    return TeamsRepository(get_incident_db(incident_id))


def _incident_personnel_repo(incident_id: str) -> IncidentPersonnelRepository:
    return IncidentPersonnelRepository(get_incident_db(incident_id))


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _infer_band(freq: float | None) -> str:
    if freq is None:
        return "Other"
    f = float(freq)
    if 3 <= f < 30:
        return "HF"
    if 30 <= f < 54:
        return "VHF-LOW"
    if 118 <= f <= 137:
        return "Air"
    if 156 <= f <= 163:
        return "Marine"
    if 54 <= f < 300:
        return "VHF"
    if 300 <= f < 700:
        return "UHF"
    if 700 <= f <= 869:
        return "700/800"
    return "Other"


# ---------------------------------------------------------------------------
# Master channel mapping
# ---------------------------------------------------------------------------

def _map_master_channel(doc: Dict[str, Any]) -> Dict[str, Any]:
    channel_id_str = str(doc.get("channel_id", ""))
    try:
        int_id = int(channel_id_str)
    except ValueError:
        int_id = None
    name = doc.get("channel_name") or ""
    freq_rx = doc.get("freq_rx")
    freq_tx = doc.get("freq_tx")
    try:
        rx_freq = float(freq_rx) if freq_rx not in (None, "") else 0.0
    except (TypeError, ValueError):
        rx_freq = 0.0
    try:
        tx_freq = float(freq_tx) if freq_tx not in (None, "") else None
    except (TypeError, ValueError):
        tx_freq = None
    return {
        "id": int_id,
        "name": name,
        "function": doc.get("function") or "Tactical",
        "rx_freq": rx_freq,
        "tx_freq": tx_freq,
        "rx_tone": doc.get("rx_tone"),
        "tx_tone": doc.get("tx_tone"),
        "system": doc.get("system"),
        "mode": doc.get("mode") or "FM",
        "notes": doc.get("notes"),
        "line_a": int(bool(doc.get("line_a", False))),
        "line_c": int(bool(doc.get("line_c", False))),
        "display_name": name or f"Ch-{int_id}",
        "band": _infer_band(rx_freq or tx_freq),
    }


# ---------------------------------------------------------------------------
# Incident channel mapping
# ---------------------------------------------------------------------------

def _channel_int_id(channel_id: str) -> Optional[int]:
    try:
        return int(str(channel_id).split("-CH-")[-1])
    except (ValueError, IndexError):
        return None


def _master_channels_by_id(repo: RadioChannelsRepository) -> Dict[str, Dict[str, Any]]:
    """All master channels keyed by their string channel_id."""
    docs = repo.find_many({})
    for d in docs:
        d.pop("_id", None)
    return {str(d.get("channel_id")): _map_master_channel(d) for d in docs}


def _map_incident_channel(doc: Dict[str, Any], master_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Combine an incident-specific plan reference with the live master channel
    definition it points to. The incident document never owns channel identity
    (name/freq/tone/mode/etc.) - that always comes from the master catalog so
    edits to the master channel are reflected immediately in every incident
    that references it.
    """
    master = master_by_id.get(str(doc.get("master_id"))) or {}
    return {
        "id": _channel_int_id(doc.get("channel_id", "")),
        "channel_id": doc.get("channel_id"),
        "master_id": doc.get("master_id"),
        "channel": master.get("name", ""),
        "function": master.get("function"),
        "band": master.get("band"),
        "system": master.get("system"),
        "mode": master.get("mode"),
        "rx_freq": master.get("rx_freq"),
        "tx_freq": master.get("tx_freq"),
        "rx_tone": master.get("rx_tone"),
        "tx_tone": master.get("tx_tone"),
        "line_a": int(bool(master.get("line_a", False))),
        "line_c": int(bool(master.get("line_c", False))),
        "encryption": doc.get("encryption", "None"),
        "assignment_division": doc.get("assignment_division"),
        "assignment_team": doc.get("assignment_team"),
        "priority": doc.get("priority", "Normal"),
        "include_on_205": int(bool(doc.get("include_on_205", True))),
        "remarks": doc.get("remarks"),
        "sort_index": doc.get("sort_index", 1000),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


def _next_channel_id(repo: IncidentChannelsRepository, incident_id: str) -> str:
    all_ids = [d.get("channel_id", "") for d in repo.find_many({"incident_id": incident_id})]
    max_n = 0
    marker = f"{incident_id}-CH-"
    for cid in all_ids:
        if isinstance(cid, str) and cid.startswith(marker):
            try:
                n = int(cid[len(marker):])
                if n > max_n:
                    max_n = n
            except ValueError:
                pass
    return f"{marker}{max_n + 1}"


# ---------------------------------------------------------------------------
# Comms log mapping
# ---------------------------------------------------------------------------

def _comms_int_id(comms_id: str, incident_id: str) -> Optional[int]:
    marker = f"{incident_id}-COMMS-"
    if isinstance(comms_id, str) and comms_id.startswith(marker):
        try:
            return int(comms_id[len(marker):])
        except ValueError:
            pass
    return None


def _parse_ref_id(value: Any, marker: str) -> Optional[int]:
    if value is None:
        return None
    s = str(value)
    if marker in s:
        try:
            return int(s.split(marker)[-1])
        except ValueError:
            pass
    try:
        return int(s)
    except ValueError:
        return None


def _map_comms_entry(doc: Dict[str, Any], incident_id: str) -> Dict[str, Any]:
    comms_id = doc.get("comms_id", "")
    attachments = doc.get("attachments")
    if isinstance(attachments, str):
        try:
            attachments = json.loads(attachments)
        except Exception:
            attachments = []
    if not isinstance(attachments, list):
        attachments = []
    return {
        "id": _comms_int_id(comms_id, incident_id),
        "comms_id": comms_id,
        "ts_utc": doc.get("ts_utc"),
        "ts_local": doc.get("ts_local"),
        "direction": doc.get("direction"),
        "priority": doc.get("priority", "Routine"),
        "resource_id": doc.get("resource_id"),
        "resource_label": doc.get("resource_label", ""),
        "frequency": doc.get("frequency", ""),
        "band": doc.get("band", ""),
        "mode": doc.get("mode", ""),
        "from_unit": doc.get("from_unit", ""),
        "to_unit": doc.get("to_unit", ""),
        "message": doc.get("message", ""),
        "action_taken": doc.get("action_taken", ""),
        "follow_up_required": bool(doc.get("follow_up_required", False)),
        "disposition": doc.get("disposition", "Open"),
        "operator_user_id": doc.get("operator_user_id"),
        "operator_display_name": doc.get("operator_display_name"),
        "team_id": _parse_ref_id(doc.get("team_id"), "-TEAM-"),
        "task_id": _parse_ref_id(doc.get("task_id"), "-TASK-"),
        "vehicle_id": doc.get("vehicle_id"),
        "personnel_id": doc.get("personnel_id"),
        "attachments": attachments,
        "geotag_lat": doc.get("geotag_lat"),
        "geotag_lon": doc.get("geotag_lon"),
        "notification_level": doc.get("notification_level"),
        "is_status_update": bool(doc.get("is_status_update", False)),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


def _next_comms_id(repo: CommunicationsLogRepository, incident_id: str) -> str:
    all_ids = [d.get("comms_id", "") for d in repo.find_many({"incident_id": incident_id})]
    max_n = 0
    marker = f"{incident_id}-COMMS-"
    for cid in all_ids:
        if isinstance(cid, str) and cid.startswith(marker):
            try:
                n = int(cid[len(marker):])
                if n > max_n:
                    max_n = n
            except ValueError:
                pass
    return f"{marker}{max_n + 1}"


def _next_preset_id(repo: CommsLogFiltersRepository, user_id: str) -> int:
    all_docs = repo.find_many({"user_id": user_id})
    return max((d.get("preset_id", 0) for d in all_docs), default=0) + 1


def _write_audit(repo: CommsLogAuditRepository, comms_id: str, action: str, changed_by: Optional[str], payload: Dict[str, Any]) -> None:
    repo.insert_one({
        "comms_id": comms_id,
        "action": action,
        "changed_by": changed_by,
        "changed_at": _utcnow(),
        "change_json": payload,
    })


# ===========================================================================
# MASTER CHANNELS
# ===========================================================================

@master_router.get("/master-channels")
def list_master_channels(
    search: Optional[str] = None,
    band: Optional[str] = None,
    mode: Optional[str] = None,
):
    repo = _radio_channels_repo()
    docs = repo.find_many({})
    for d in docs:
        d.pop("_id", None)
    results = [_map_master_channel(d) for d in docs]
    if search:
        s = search.lower()
        results = [r for r in results if s in f"{r['name']} {r.get('function', '')} {r.get('notes', '')}".lower()]
    if band:
        results = [r for r in results if r.get("band") == band]
    if mode:
        results = [r for r in results if r.get("mode") == mode]
    return results


@master_router.get("/master-channels/{channel_id}")
def get_master_channel(channel_id: int):
    repo = _radio_channels_repo()
    doc = repo.find_one({"channel_id": str(channel_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Channel not found")
    doc.pop("_id", None)
    return _map_master_channel(doc)


_MASTER_CHANNEL_FIELD_MAP = {
    "name": "channel_name",
    "function": "function",
    "rx_freq": "freq_rx",
    "tx_freq": "freq_tx",
    "rx_tone": "rx_tone",
    "tx_tone": "tx_tone",
    "system": "system",
    "mode": "mode",
    "notes": "notes",
    "line_a": "line_a",
    "line_c": "line_c",
}


def _next_master_channel_id(repo: RadioChannelsRepository) -> str:
    max_id = 0
    for d in repo.find_many({}):
        try:
            n = int(str(d.get("channel_id", "0")))
            if n > max_id:
                max_id = n
        except (ValueError, TypeError):
            pass
    return str(max_id + 1)


@master_router.post("/master-channels")
def create_master_channel(body: Dict[str, Any] = Body(...)):
    repo = _radio_channels_repo()
    new_id = _next_master_channel_id(repo)
    doc = {
        "channel_id": new_id,
        "channel_name": str(body.get("name") or "").strip(),
        "function": body.get("function"),
        "freq_rx": body.get("rx_freq"),
        "freq_tx": body.get("tx_freq"),
        "rx_tone": body.get("rx_tone"),
        "tx_tone": body.get("tx_tone"),
        "system": body.get("system"),
        "mode": body.get("mode") or "FM",
        "notes": body.get("notes"),
        "line_a": bool(body.get("line_a", False)),
        "line_c": bool(body.get("line_c", False)),
    }
    doc = repo.insert_one(doc)
    doc.pop("_id", None)
    return _map_master_channel(doc)


@master_router.patch("/master-channels/{channel_id}")
def update_master_channel(channel_id: int, patch: Dict[str, Any] = Body(...)):
    repo = _radio_channels_repo()
    doc = repo.find_one({"channel_id": str(channel_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Channel not found")
    update: Dict[str, Any] = {}
    for api_key, mongo_key in _MASTER_CHANNEL_FIELD_MAP.items():
        if api_key in patch:
            update[mongo_key] = patch[api_key]
    repo.update_one(doc["_id"], update)
    updated = repo.find_by_id(doc["_id"])
    updated.pop("_id", None)
    return _map_master_channel(updated)


@master_router.delete("/master-channels/{channel_id}")
def delete_master_channel(channel_id: int):
    repo = _radio_channels_repo()
    doc = repo.find_one({"channel_id": str(channel_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Channel not found")
    repo.delete_one(doc["_id"])
    return {"deleted": True}


# ===========================================================================
# INCIDENT CHANNELS (ICS 205)
# ===========================================================================

# NOTE: /validate and /preview must be declared before /{row_id} so FastAPI
# matches them before trying to coerce the literal string into an integer.

@incident_router.get("/incidents/{incident_id}/channels-plan/validate")
def validate_channels_plan(incident_id: str):
    repo = _incident_channels_repo(incident_id)
    master_by_id = _master_channels_by_id(_radio_channels_repo())
    docs = repo.find_many(
        {"incident_id": incident_id, "deleted": {"$ne": True}},
        sort=[("sort_index", 1), ("channel_id", 1)],
    )
    for d in docs:
        d.pop("_id", None)
    rows = [_map_incident_channel(d, master_by_id) for d in docs]
    messages = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            if (a.get("band") == b.get("band") and a.get("mode") == b.get("mode")
                    and a.get("rx_freq") == b.get("rx_freq")
                    and (a.get("tx_freq") or 0) == (b.get("tx_freq") or 0)
                    and (a.get("rx_tone") or "") == (b.get("rx_tone") or "")
                    and (a.get("tx_tone") or "") == (b.get("tx_tone") or "")):
                messages.append({
                    "level": "conflict",
                    "text": f"Duplicate freq {a.get('rx_freq')} ({a.get('channel')} & {b.get('channel')})",
                })
    for r in rows:
        if not r.get("function"):
            messages.append({"level": "warning", "text": f"{r.get('channel')} missing function"})
        if r.get("function", "").lower() == "tactical" and (not r.get("assignment_division") or not r.get("assignment_team")):
            messages.append({"level": "warning", "text": f"{r.get('channel')} missing assignment"})
        inferred = _infer_band(r.get("rx_freq") or r.get("tx_freq"))
        if inferred != r.get("band"):
            messages.append({"level": "warning", "text": f"{r.get('channel')} out of band"})
    return {
        "messages": messages,
        "conflicts": sum(1 for m in messages if m["level"] == "conflict"),
        "warnings": sum(1 for m in messages if m["level"] == "warning"),
    }


@incident_router.get("/incidents/{incident_id}/channels-plan/preview")
def preview_channels_plan(incident_id: str):
    repo = _incident_channels_repo(incident_id)
    master_by_id = _master_channels_by_id(_radio_channels_repo())
    docs = repo.find_many(
        {"incident_id": incident_id, "deleted": {"$ne": True}},
        sort=[("sort_index", 1), ("channel_id", 1)],
    )
    for d in docs:
        d.pop("_id", None)
    rows = [_map_incident_channel(d, master_by_id) for d in docs]
    preview = []
    for r in rows:
        assignment = " / ".join([p for p in [r.get("assignment_division"), r.get("assignment_team")] if p])
        if r.get("rx_tone") == r.get("tx_tone"):
            tone = r.get("rx_tone") or ""
        else:
            tone = "/".join(filter(None, [r.get("rx_tone"), r.get("tx_tone")]))
        preview.append({
            "Function": r.get("function"),
            "Channel": r.get("channel"),
            "Assignment": assignment,
            "RX": r.get("rx_freq"),
            "TX": r.get("tx_freq"),
            "ToneNAC": tone or "",
            "Mode": r.get("mode"),
            "Encryption": r.get("encryption", "None"),
            "Notes": r.get("remarks", ""),
        })
    return preview


# NOTE: /instance must be declared before /{row_id} for the same reason as
# /validate and /preview above - it shares the same single-segment path
# shape and would otherwise be swallowed by the int-coercing {row_id} routes.

class ICS205InstanceRequest(BaseModel):
    special_instructions: str = ""
    op_period_id: Optional[str] = None


@incident_router.get("/incidents/{incident_id}/channels-plan/instance")
def get_ics205_instance(incident_id: str):
    repo = _ics205_instance_repo(incident_id)
    doc = repo.find_one({"incident_id": incident_id})
    if not doc:
        return {"special_instructions": "", "op_period_id": None}
    return {
        "special_instructions": doc.get("special_instructions", ""),
        "op_period_id": doc.get("op_period_id"),
    }


@incident_router.put("/incidents/{incident_id}/channels-plan/instance")
def save_ics205_instance(incident_id: str, body: ICS205InstanceRequest):
    repo = _ics205_instance_repo(incident_id)
    existing = repo.find_one({"incident_id": incident_id})
    update = {
        "special_instructions": body.special_instructions,
        "op_period_id": body.op_period_id,
    }
    if existing:
        repo.update_one(existing["_id"], update)
    else:
        update["incident_id"] = incident_id
        repo.insert_one(update)
    return update


@incident_router.get("/incidents/{incident_id}/channels-plan")
def list_channels_plan(incident_id: str):
    repo = _incident_channels_repo(incident_id)
    master_by_id = _master_channels_by_id(_radio_channels_repo())
    docs = repo.find_many(
        {"incident_id": incident_id, "deleted": {"$ne": True}},
        sort=[("sort_index", 1), ("channel_id", 1)],
    )
    for d in docs:
        d.pop("_id", None)
    return [_map_incident_channel(d, master_by_id) for d in docs]


# Incident-specific fields a plan reference is allowed to carry. Channel
# identity (name/freq/tone/mode/etc.) always lives on the master channel and
# is never copied or patched here - the plan only ever stores a pointer
# (master_id) plus how this incident is using that channel.
_PLAN_PATCHABLE_FIELDS = {
    "assignment_division", "assignment_team", "priority", "encryption",
    "remarks", "include_on_205", "sort_index",
}


class AddFromMasterRequest(BaseModel):
    master_id: int
    defaults: Dict[str, Any] = {}


@incident_router.post("/incidents/{incident_id}/channels-plan", status_code=201)
def add_channel_from_master(incident_id: str, body: AddFromMasterRequest):
    defaults = body.defaults or {}
    repo = _incident_channels_repo(incident_id)
    master_doc = _radio_channels_repo().find_one({"channel_id": str(body.master_id)})
    if not master_doc:
        raise HTTPException(status_code=404, detail="Master channel not found")
    channel_id = _next_channel_id(repo, incident_id)
    doc = {
        "channel_id": channel_id,
        "incident_id": incident_id,
        "master_id": str(body.master_id),
        "encryption": defaults.get("encryption", "None"),
        "assignment_division": defaults.get("assignment_division"),
        "assignment_team": defaults.get("assignment_team"),
        "priority": defaults.get("priority", "Normal"),
        "include_on_205": bool(defaults.get("include_on_205", True)),
        "remarks": defaults.get("remarks"),
        "sort_index": int(defaults.get("sort_index", 1000)),
        "deleted": False,
    }
    doc = repo.insert_one(doc)
    doc.pop("_id", None)
    return _map_incident_channel(doc, _master_channels_by_id(_radio_channels_repo()))


@incident_router.get("/incidents/{incident_id}/channels-plan/{row_id}")
def get_channel_plan_row(incident_id: str, row_id: int):
    repo = _incident_channels_repo(incident_id)
    channel_id = f"{incident_id}-CH-{row_id}"
    doc = repo.find_one({"channel_id": channel_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Channel not found")
    doc.pop("_id", None)
    return _map_incident_channel(doc, _master_channels_by_id(_radio_channels_repo()))


@incident_router.put("/incidents/{incident_id}/channels-plan/{row_id}")
def update_channel_plan_row(incident_id: str, row_id: int, patch: Dict[str, Any] = Body(...)):
    repo = _incident_channels_repo(incident_id)
    channel_id = f"{incident_id}-CH-{row_id}"
    existing = repo.find_one({"channel_id": channel_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Channel not found")
    update = {k: v for k, v in patch.items() if k in _PLAN_PATCHABLE_FIELDS}
    repo.update_one(existing["_id"], update)
    doc = repo.find_by_id(existing["_id"])
    doc.pop("_id", None)
    return _map_incident_channel(doc, _master_channels_by_id(_radio_channels_repo()))


@incident_router.delete("/incidents/{incident_id}/channels-plan/{row_id}", status_code=204)
def delete_channel_plan_row(incident_id: str, row_id: int):
    repo = _incident_channels_repo(incident_id)
    channel_id = f"{incident_id}-CH-{row_id}"
    existing = repo.find_one({"channel_id": channel_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Channel not found")
    repo.update_one(existing["_id"], {"deleted": True})


class ReorderRequest(BaseModel):
    direction: str


@incident_router.patch("/incidents/{incident_id}/channels-plan/{row_id}/reorder")
def reorder_channel(incident_id: str, row_id: int, body: ReorderRequest):
    repo = _incident_channels_repo(incident_id)
    channel_id = f"{incident_id}-CH-{row_id}"
    doc = repo.find_one({"channel_id": channel_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Channel not found")
    delta = -1 if body.direction == "up" else 1
    new_index = int(doc.get("sort_index", 1000)) + delta
    repo.update_one(doc["_id"], {"sort_index": new_index})


# ===========================================================================
# TRAFFIC LOG (communications_log)
# ===========================================================================

@incident_router.get("/incidents/{incident_id}/comms-log/contacts")
def list_comms_contacts(incident_id: str):
    teams_repo = _teams_repo(incident_id)
    personnel_repo = _incident_personnel_repo(incident_id)
    suggestions: List[Dict[str, Any]] = []

    for doc in teams_repo.find_many({"deleted": {"$ne": True}}):
        doc.pop("_id", None)
        team_id_str = doc.get("team_id", "")
        int_id = _parse_ref_id(team_id_str, "-TEAM-")
        name = doc.get("name") or doc.get("team_name") or ""
        callsign = doc.get("callsign") or ""
        display = name or callsign or f"Team {int_id}"
        alias_values = [v for v in (name, callsign) if v]
        secondary = " / ".join([v for v in alias_values if v != display])
        suggestions.append({"type": "team", "id": int_id, "primary": display, "secondary": secondary, "aliases": alias_values})

    for doc in personnel_repo.find_many({"incident_id": incident_id, "deleted": {"$ne": True}}):
        doc.pop("_id", None)
        # Personnel are referenced by their master roster id (see the
        # master/incident-personnel sync chain in operations.py), not a
        # per-incident "-PERSON-" formatted string.
        int_id = doc.get("master_id")
        if int_id is None:
            int_id = _parse_ref_id(doc.get("personnel_id", ""), "-PERSON-")
        name = doc.get("name") or ""
        role = doc.get("role") or doc.get("position") or ""
        callsign = doc.get("callsign") or ""
        primary = role or name or callsign or f"Personnel {int_id}"
        secondary = " / ".join([v for v in (name, callsign) if v and v != primary])
        suggestions.append({"type": "personnel", "id": int_id, "primary": primary, "secondary": secondary, "aliases": [v for v in (role, name, callsign) if v]})

    return suggestions


@incident_router.get("/incidents/{incident_id}/comms-log-filters")
def list_filter_presets(incident_id: str, user_id: Optional[str] = None):
    if not user_id:
        return []
    repo = _comms_filters_repo(incident_id)
    docs = repo.find_many({"user_id": user_id}, sort=[("name", 1)])
    for d in docs:
        d.pop("_id", None)
    return docs


class FilterPresetRequest(BaseModel):
    name: str
    filters: Dict[str, Any]
    preset_id: Optional[int] = None
    user_id: Optional[str] = None


@incident_router.post("/incidents/{incident_id}/comms-log-filters", status_code=201)
def save_filter_preset(incident_id: str, body: FilterPresetRequest):
    if not body.user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    repo = _comms_filters_repo(incident_id)
    if body.preset_id is None:
        preset_id = _next_preset_id(repo, body.user_id)
        repo.insert_one({
            "preset_id": preset_id,
            "incident_id": incident_id,
            "name": body.name,
            "user_id": body.user_id,
            "filters": body.filters,
        })
    else:
        preset_id = body.preset_id
        existing = repo.find_one({"preset_id": body.preset_id, "user_id": body.user_id})
        if existing:
            repo.update_one(existing["_id"], {"name": body.name, "filters": body.filters})
    doc = repo.find_one({"preset_id": preset_id, "user_id": body.user_id})
    if doc:
        doc.pop("_id", None)
    return doc


@incident_router.delete("/incidents/{incident_id}/comms-log-filters/{preset_id}", status_code=204)
def delete_filter_preset(incident_id: str, preset_id: int, user_id: Optional[str] = None):
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    repo = _comms_filters_repo(incident_id)
    existing = repo.find_one({"preset_id": preset_id, "user_id": user_id})
    if existing:
        repo.delete_one(existing["_id"])


@incident_router.get("/incidents/{incident_id}/comms-log/{entry_id}/audit")
def list_comms_audit(incident_id: str, entry_id: int):
    repo = _comms_audit_repo(incident_id)
    comms_id = f"{incident_id}-COMMS-{entry_id}"
    docs = repo.find_many({"comms_id": comms_id}, sort=[("changed_at", -1)])
    for d in docs:
        d.pop("_id", None)
    return docs


@incident_router.get("/incidents/{incident_id}/comms-log")
def list_comms_log(
    incident_id: str,
    start_ts_utc: Optional[str] = None,
    end_ts_utc: Optional[str] = None,
    priorities: Optional[str] = None,
    dispositions: Optional[str] = None,
    is_status_update: Optional[bool] = None,
    follow_up_required: Optional[bool] = None,
    text_search: Optional[str] = None,
    order_by: str = "ts_utc",
    order_desc: bool = True,
    limit: Optional[int] = None,
    offset: int = 0,
):
    repo = _comms_log_repo(incident_id)
    query: Dict[str, Any] = {"incident_id": incident_id, "deleted": {"$ne": True}}
    if start_ts_utc and end_ts_utc:
        query["ts_utc"] = {"$gte": start_ts_utc, "$lte": end_ts_utc}
    elif start_ts_utc:
        query["ts_utc"] = {"$gte": start_ts_utc}
    elif end_ts_utc:
        query["ts_utc"] = {"$lte": end_ts_utc}
    if priorities:
        query["priority"] = {"$in": [p.strip() for p in priorities.split(",")]}
    if dispositions:
        query["disposition"] = {"$in": [d.strip() for d in dispositions.split(",")]}
    if is_status_update is not None:
        query["is_status_update"] = is_status_update
    if follow_up_required is not None:
        query["follow_up_required"] = follow_up_required
    if text_search:
        pattern = text_search
        query["$or"] = [
            {"message": {"$regex": pattern, "$options": "i"}},
            {"action_taken": {"$regex": pattern, "$options": "i"}},
            {"from_unit": {"$regex": pattern, "$options": "i"}},
            {"to_unit": {"$regex": pattern, "$options": "i"}},
        ]
    _valid_order_fields = {"ts_utc", "ts_local", "priority", "resource_label", "created_at"}
    sort_field = order_by if order_by in _valid_order_fields else "ts_utc"
    sort_dir = -1 if order_desc else 1
    docs = repo.find_many(query, sort=[(sort_field, sort_dir)], skip=offset or 0, limit=limit or 0)
    for d in docs:
        d.pop("_id", None)
    return [_map_comms_entry(d, incident_id) for d in docs]


class CommsLogEntryRequest(BaseModel):
    message: str
    ts_utc: Optional[str] = None
    ts_local: Optional[str] = None
    direction: Optional[str] = None
    priority: str = "Routine"
    resource_id: Optional[int] = None
    resource_label: str = ""
    frequency: str = ""
    band: str = ""
    mode: str = ""
    from_unit: str = ""
    to_unit: str = ""
    action_taken: str = ""
    follow_up_required: bool = False
    disposition: str = "Open"
    operator_user_id: Optional[str] = None
    operator_display_name: Optional[str] = None
    team_id: Optional[int] = None
    task_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    personnel_id: Optional[int] = None
    attachments: List[str] = []
    geotag_lat: Optional[float] = None
    geotag_lon: Optional[float] = None
    notification_level: Optional[str] = None
    is_status_update: bool = False


@incident_router.post("/incidents/{incident_id}/comms-log", status_code=201)
def add_comms_log_entry(incident_id: str, body: CommsLogEntryRequest):
    repo = _comms_log_repo(incident_id)
    audit_repo = _comms_audit_repo(incident_id)
    now = _utcnow()
    comms_id = _next_comms_id(repo, incident_id)
    doc = {
        "comms_id": comms_id,
        "incident_id": incident_id,
        "ts_utc": body.ts_utc or now,
        "ts_local": body.ts_local or now,
        "direction": body.direction,
        "priority": body.priority,
        "resource_id": body.resource_id,
        "resource_label": body.resource_label or "",
        "frequency": body.frequency or "",
        "band": body.band or "",
        "mode": body.mode or "",
        "from_unit": body.from_unit or "",
        "to_unit": body.to_unit or "",
        "message": body.message,
        "action_taken": body.action_taken or "",
        "follow_up_required": body.follow_up_required,
        "disposition": body.disposition or "Open",
        "operator_user_id": body.operator_user_id,
        "operator_display_name": body.operator_display_name,
        "team_id": f"{incident_id}-TEAM-{body.team_id}" if body.team_id is not None else None,
        "task_id": f"{incident_id}-TASK-{body.task_id}" if body.task_id is not None else None,
        "vehicle_id": body.vehicle_id,
        "personnel_id": body.personnel_id,
        "attachments": body.attachments or [],
        "geotag_lat": body.geotag_lat,
        "geotag_lon": body.geotag_lon,
        "notification_level": body.notification_level,
        "is_status_update": body.is_status_update,
        "deleted": False,
    }
    saved = repo.insert_one(doc)
    saved.pop("_id", None)
    _write_audit(audit_repo, comms_id, "create", body.operator_user_id, {"message": body.message})
    return _map_comms_entry(saved, incident_id)


@incident_router.get("/incidents/{incident_id}/comms-log/{entry_id}")
def get_comms_log_entry(incident_id: str, entry_id: int):
    repo = _comms_log_repo(incident_id)
    comms_id = f"{incident_id}-COMMS-{entry_id}"
    doc = repo.find_one({"comms_id": comms_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Entry not found")
    doc.pop("_id", None)
    return _map_comms_entry(doc, incident_id)


@incident_router.patch("/incidents/{incident_id}/comms-log/{entry_id}")
def update_comms_log_entry(incident_id: str, entry_id: int, patch: Dict[str, Any] = Body(...)):
    repo = _comms_log_repo(incident_id)
    audit_repo = _comms_audit_repo(incident_id)
    comms_id = f"{incident_id}-COMMS-{entry_id}"
    doc = repo.find_one({"comms_id": comms_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Entry not found")
    update = dict(patch)
    if "follow_up_required" in update:
        update["follow_up_required"] = bool(update["follow_up_required"])
    if "is_status_update" in update:
        update["is_status_update"] = bool(update["is_status_update"])
    if "team_id" in update and update["team_id"] is not None:
        update["team_id"] = f"{incident_id}-TEAM-{update['team_id']}"
    if "task_id" in update and update["task_id"] is not None:
        update["task_id"] = f"{incident_id}-TASK-{update['task_id']}"
    repo.update_one(doc["_id"], update)
    updated = repo.find_by_id(doc["_id"])
    updated.pop("_id", None)
    changed_by = patch.get("operator_user_id") or doc.get("operator_user_id")
    _write_audit(audit_repo, comms_id, "update", changed_by, patch)
    return _map_comms_entry(updated, incident_id)


@incident_router.delete("/incidents/{incident_id}/comms-log/{entry_id}", status_code=204)
def delete_comms_log_entry(incident_id: str, entry_id: int):
    repo = _comms_log_repo(incident_id)
    audit_repo = _comms_audit_repo(incident_id)
    comms_id = f"{incident_id}-COMMS-{entry_id}"
    doc = repo.find_one({"comms_id": comms_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Entry not found")
    repo.update_one(doc["_id"], {"deleted": True})
    _write_audit(audit_repo, comms_id, "delete", doc.get("operator_user_id"), {})
