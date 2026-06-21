"""Liaison repository — proxies through the SARApp API server (MongoDB backend)."""
from __future__ import annotations

from typing import Any

from utils import incident_context
from utils.state import AppState


def _resolve_incident_id(incident_id: object | None = None) -> str:
    value = incident_id or incident_context.get_active_incident_id() or AppState.get_active_incident()
    if not value:
        raise RuntimeError("No active incident selected for Liaison data")
    return str(value)


# ---------------------------------------------------------------------------
# Agencies
# ---------------------------------------------------------------------------

def fetch_agency_rows(incident_id: object | None = None) -> list[dict[str, Any]]:
    from utils.api_client import api_client
    iid = _resolve_incident_id(incident_id)
    return api_client.get(f"/api/incidents/{iid}/liaison/agency-rows")


def fetch_agency_detail(agency_id: int, incident_id: object | None = None) -> dict[str, Any]:
    from utils.api_client import api_client
    iid = _resolve_incident_id(incident_id)
    return api_client.get(f"/api/incidents/{iid}/liaison/agencies/{agency_id}/detail")


def create_agency(values: dict[str, Any], incident_id: object | None = None) -> dict[str, Any]:
    from utils.api_client import api_client
    iid = _resolve_incident_id(incident_id)
    return api_client.post(f"/api/incidents/{iid}/liaison/agencies", json=values)


def update_agency_status(agency_id: int, status: str, incident_id: object | None = None) -> dict[str, Any]:
    from utils.api_client import api_client
    iid = _resolve_incident_id(incident_id)
    return api_client.patch(
        f"/api/incidents/{iid}/liaison/agencies/{agency_id}/status",
        json={"current_status": status},
    )


# ---------------------------------------------------------------------------
# Interactions
# ---------------------------------------------------------------------------

def create_interaction(values: dict[str, Any], incident_id: object | None = None) -> dict[str, Any]:
    from utils.api_client import api_client
    iid = _resolve_incident_id(incident_id)
    return api_client.post(f"/api/incidents/{iid}/liaison/interactions", json=values)


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

def fetch_feedback_rows(incident_id: object | None = None) -> list[dict[str, Any]]:
    from utils.api_client import api_client
    iid = _resolve_incident_id(incident_id)
    return api_client.get(f"/api/incidents/{iid}/liaison/feedback-rows")


def create_feedback(values: dict[str, Any], incident_id: object | None = None) -> dict[str, Any]:
    from utils.api_client import api_client
    iid = _resolve_incident_id(incident_id)
    return api_client.post(f"/api/incidents/{iid}/liaison/feedback", json=values)
