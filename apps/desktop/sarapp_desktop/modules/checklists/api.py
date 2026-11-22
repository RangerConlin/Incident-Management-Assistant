"""Thin HTTP wrapper around the server's shared Checklist API.

This module is the only place in the desktop app that knows the Checklist
endpoints' URL shapes (`server/sarapp_db/sarapp_db/api/routers/checklists.py`
/ `checklist_templates.py`, Phases 4A/4B). Every widget under
`modules/checklists/` calls through here rather than touching
`utils.api_client` directly — the same service-layer-over-api_client
layering `modules/plannedtoolkit/services.py` already uses.

Every write passes the desktop's current actor identity
(`AppState.get_active_user_id()` / `get_active_api_session_id()`) as JSON
body fields. There is no Authorization header anywhere in this desktop app
(`utils/api_client.py` sets none); the server instead resolves "who did
this" from the active desktop session the same way `approvals.py` already
does for signing an approval step — this is simply that same convention
applied to a new endpoint family, not a new auth mechanism.
"""

from __future__ import annotations

from typing import Any, Optional

from utils.api_client import api_client
from utils.state import AppState

from .name_display import format_person_display

_person_display_cache: dict[int, str] = {}


def _actor_fields() -> dict[str, Any]:
    fields: dict[str, Any] = {}
    uid = AppState.get_active_user_id()
    if uid:
        try:
            fields["actor_id"] = int(uid)
        except (TypeError, ValueError):
            pass
    session_id = AppState.get_active_api_session_id()
    if session_id:
        fields["session_id"] = session_id
    return fields


def current_actor_id() -> Optional[int]:
    uid = AppState.get_active_user_id()
    try:
        return int(uid) if uid else None
    except (TypeError, ValueError):
        return None


def resolve_person_display(person_record: Optional[int]) -> str:
    """"F. Last" display for a person_record, cached for this process.

    Mirrors `record_resolvers.resolve_personnel_name`'s "thin,
    failure-tolerant read through the existing API" shape but formats with
    `name_display.format_person_display` so it matches the checklist
    system's own convention rather than returning a bare stored name.
    """

    if person_record is None:
        return ""
    if person_record in _person_display_cache:
        return _person_display_cache[person_record]
    fallback = str(person_record)
    try:
        person = api_client.get(f"/api/master/personnel/{person_record}")
    except Exception:
        person = None
    if not person:
        display = fallback
    else:
        display = format_person_display(
            person.get("first_name"), person.get("last_name"), fallback=fallback
        ) or str(person.get("name") or person.get("full_name") or fallback)
    _person_display_cache[person_record] = display
    return display


# ---------------------------------------------------------------------------
# Catalog templates — read-only from this module's point of view; template
# management itself stays entirely in the existing catalog UI, never
# duplicated here.
# ---------------------------------------------------------------------------

def list_templates(*, category: Optional[str] = None, include_inactive: bool = False) -> list[dict]:
    params: dict[str, Any] = {"include_inactive": include_inactive}
    if category:
        params["category"] = category
    return api_client.get("/api/checklist-templates", params=params) or []


def list_template_categories() -> list[str]:
    return api_client.get("/api/checklist-templates/categories") or []


def get_template(template_id: int) -> dict:
    return api_client.get(f"/api/checklist-templates/{template_id}")


# ---------------------------------------------------------------------------
# Instances
# ---------------------------------------------------------------------------

def list_checklists(
    incident_id: str,
    *,
    status: Optional[str] = None,
    owner_person_record: Optional[int] = None,
    template_id: Optional[int] = None,
) -> list[dict]:
    params: dict[str, Any] = {
        "status": status,
        "owner_person_record": owner_person_record,
        "template_id": template_id,
    }
    params = {key: value for key, value in params.items() if value is not None}
    return api_client.get(f"/api/incidents/{incident_id}/checklists", params=params) or []


def get_checklist(incident_id: str, checklist_id: str) -> dict:
    return api_client.get(f"/api/incidents/{incident_id}/checklists/{checklist_id}")


def create_blank_checklist(
    incident_id: str,
    *,
    name: str,
    sections: list[dict],
    description: str = "",
    instructions: str = "",
    owner_person_record: Optional[int] = None,
) -> dict:
    payload = {
        "name": name,
        "description": description,
        "instructions": instructions,
        "sections": sections,
        "owner_person_record": owner_person_record,
        **_actor_fields(),
    }
    return api_client.post(f"/api/incidents/{incident_id}/checklists", json=payload)


def create_checklist_from_template(
    incident_id: str,
    *,
    template_id: int,
    name: Optional[str] = None,
    owner_person_record: Optional[int] = None,
) -> dict:
    payload = {
        "template_id": template_id,
        "name": name,
        "owner_person_record": owner_person_record,
        **_actor_fields(),
    }
    return api_client.post(f"/api/incidents/{incident_id}/checklists/from-template", json=payload)


def record_item_response(
    incident_id: str,
    checklist_id: str,
    item_id: str,
    *,
    value: Any = None,
    na: bool = False,
    notes: str = "",
) -> dict:
    payload = {"value": value, "na": na, "notes": notes, **_actor_fields()}
    return api_client.post(
        f"/api/incidents/{incident_id}/checklists/{checklist_id}/items/{item_id}/responses", json=payload
    )


def get_item_history(incident_id: str, checklist_id: str, item_id: str) -> dict:
    return api_client.get(
        f"/api/incidents/{incident_id}/checklists/{checklist_id}/items/{item_id}/responses"
    )


def get_progress(incident_id: str, checklist_id: str) -> dict:
    return api_client.get(f"/api/incidents/{incident_id}/checklists/{checklist_id}/progress")


def validate_completion(incident_id: str, checklist_id: str) -> dict:
    return api_client.post(
        f"/api/incidents/{incident_id}/checklists/{checklist_id}/validate-completion", json=_actor_fields()
    )


def complete_checklist(
    incident_id: str,
    checklist_id: str,
    *,
    acknowledge_failures: bool = False,
    stream: Optional[dict] = None,
) -> dict:
    payload = {"acknowledge_failures": acknowledge_failures, "stream": stream, **_actor_fields()}
    return api_client.post(f"/api/incidents/{incident_id}/checklists/{checklist_id}/complete", json=payload)


def reopen_checklist(
    incident_id: str, checklist_id: str, *, reason: str, stream: Optional[dict] = None
) -> dict:
    payload = {"reason": reason, "stream": stream, **_actor_fields()}
    return api_client.post(f"/api/incidents/{incident_id}/checklists/{checklist_id}/reopen", json=payload)


def archive_checklist(incident_id: str, checklist_id: str) -> dict:
    return api_client.post(
        f"/api/incidents/{incident_id}/checklists/{checklist_id}/archive", json=_actor_fields()
    )


def get_lifecycle_history(incident_id: str, checklist_id: str) -> dict:
    return api_client.get(
        f"/api/incidents/{incident_id}/checklists/{checklist_id}/lifecycle-history",
        params=_actor_fields(),
    )


def get_completion_summary(incident_id: str, checklist_id: str) -> dict:
    return api_client.get(f"/api/incidents/{incident_id}/checklists/{checklist_id}/completion-summary")


# ---------------------------------------------------------------------------
# ICS-214 stream options
# ---------------------------------------------------------------------------

def list_stream_options(incident_id: str) -> list[dict]:
    """Named, selectable ICS-214 streams for this incident.

    One entry per saved log definition (builtin + custom) and one per
    incident org unit, each carrying the exact
    ``{log_keys, org_unit_ids, incident_wide}`` payload `complete`/`reopen`
    expect as ``stream`` — a read-only projection of `ics214.py`'s own
    existing data, never a second section/unit hierarchy.
    """

    options: list[dict] = [{"label": "Incident-wide", "stream": {"incident_wide": True}}]

    try:
        definitions = api_client.get(f"/api/incidents/{incident_id}/ics214/log-definitions") or []
    except Exception:
        definitions = []
    for definition in definitions:
        log_keys = (definition.get("filters") or {}).get("log_keys") or []
        if not log_keys:
            continue
        label = definition.get("name") or definition.get("id") or "Log"
        options.append({"label": str(label), "stream": {"log_keys": list(log_keys)}})

    try:
        association_options = api_client.get(f"/api/incidents/{incident_id}/ics214/association-options") or {}
    except Exception:
        association_options = {}
    for row in association_options.get("org_unit_ids") or []:
        if row.get("archived"):
            continue
        label = row.get("label") or f"Org unit {row.get('id')}"
        options.append({"label": str(label), "stream": {"org_unit_ids": [row["id"]]}})

    return options
