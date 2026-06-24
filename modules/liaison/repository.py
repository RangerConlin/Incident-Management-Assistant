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
# Agency requests
# ---------------------------------------------------------------------------

def fetch_agency_requests(agency_id: int | None = None, incident_id: object | None = None) -> list[dict[str, Any]]:
    from utils.api_client import api_client
    iid = _resolve_incident_id(incident_id)
    params = {"agency_id": agency_id} if agency_id is not None else None
    return api_client.get(f"/api/incidents/{iid}/liaison/agency-requests", params=params)


def create_agency_request(values: dict[str, Any], incident_id: object | None = None) -> dict[str, Any]:
    from utils.api_client import api_client
    iid = _resolve_incident_id(incident_id)
    return api_client.post(f"/api/incidents/{iid}/liaison/agency-requests", json=values)


# ---------------------------------------------------------------------------
# Resource offers
# ---------------------------------------------------------------------------

def fetch_resource_offers(agency_id: int | None = None, incident_id: object | None = None) -> list[dict[str, Any]]:
    from utils.api_client import api_client
    iid = _resolve_incident_id(incident_id)
    params = {"agency_id": agency_id} if agency_id is not None else None
    return api_client.get(f"/api/incidents/{iid}/liaison/resource-offers", params=params)


def create_resource_offer(values: dict[str, Any], incident_id: object | None = None) -> dict[str, Any]:
    from utils.api_client import api_client
    iid = _resolve_incident_id(incident_id)
    return api_client.post(f"/api/incidents/{iid}/liaison/resource-offers", json=values)


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


def _fetch_feedback_for(field: str, value: int, incident_id: object | None) -> list[dict[str, Any]]:
    from utils.api_client import api_client
    iid = _resolve_incident_id(incident_id)
    return api_client.get(f"/api/incidents/{iid}/liaison/feedback", params={field: value})


def fetch_feedback_for_objective(objective_id: int, incident_id: object | None = None) -> list[dict[str, Any]]:
    return _fetch_feedback_for("objective_id", objective_id, incident_id)


def fetch_feedback_for_strategy(strategy_id: int, incident_id: object | None = None) -> list[dict[str, Any]]:
    return _fetch_feedback_for("strategy_id", strategy_id, incident_id)


def fetch_feedback_for_task(task_id: int, incident_id: object | None = None) -> list[dict[str, Any]]:
    return _fetch_feedback_for("task_id", task_id, incident_id)


def fetch_feedback_for_resource_request(resource_request_id: int, incident_id: object | None = None) -> list[dict[str, Any]]:
    return _fetch_feedback_for("resource_request_id", resource_request_id, incident_id)
