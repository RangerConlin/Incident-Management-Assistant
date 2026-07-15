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


def mark_agency_request_converted(
    request_id: int,
    converted_to_type: str,
    converted_to_id: str,
    incident_id: object | None = None,
) -> dict[str, Any]:
    from utils.api_client import api_client
    iid = _resolve_incident_id(incident_id)
    return api_client.patch(
        f"/api/incidents/{iid}/liaison/agency-requests/{request_id}/converted",
        json={"converted_to_type": converted_to_type, "converted_to_id": converted_to_id},
    )


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


# ---------------------------------------------------------------------------
# Reporting digests (Reporting Board)
# ---------------------------------------------------------------------------

def fetch_reporting_digests(incident_id: object | None = None) -> list[dict[str, Any]]:
    from utils.api_client import api_client
    iid = _resolve_incident_id(incident_id)
    return api_client.get(f"/api/incidents/{iid}/liaison/reporting-digests")


def create_reporting_digest(
    source_type: str,
    source_id: str,
    updated_by: str = "",
    incident_id: object | None = None,
) -> dict[str, Any]:
    from utils.api_client import api_client
    iid = _resolve_incident_id(incident_id)
    return api_client.post(
        f"/api/incidents/{iid}/liaison/reporting-digests",
        json={"source_type": source_type, "source_id": source_id, "updated_by": updated_by},
    )


def update_reporting_digest(
    digest_id: int,
    values: dict[str, Any],
    incident_id: object | None = None,
) -> dict[str, Any]:
    from utils.api_client import api_client
    iid = _resolve_incident_id(incident_id)
    return api_client.patch(f"/api/incidents/{iid}/liaison/reporting-digests/{digest_id}", json=values)


def resync_reporting_digest(digest_id: int, incident_id: object | None = None) -> dict[str, Any]:
    from utils.api_client import api_client
    iid = _resolve_incident_id(incident_id)
    return api_client.post(f"/api/incidents/{iid}/liaison/reporting-digests/{digest_id}/resync", json={})


def delete_reporting_digest(digest_id: int, incident_id: object | None = None) -> None:
    from utils.api_client import api_client
    iid = _resolve_incident_id(incident_id)
    api_client.delete(f"/api/incidents/{iid}/liaison/reporting-digests/{digest_id}")


# ---------------------------------------------------------------------------
# Convert a customer request into an Objective or Task
# ---------------------------------------------------------------------------

def convert_agency_request_to_objective(
    request_text: str,
    request_id: int,
    priority: str = "normal",
    user_id: str | None = None,
    incident_id: object | None = None,
) -> dict[str, Any]:
    from modules.command.models.objectives import ApiObjectiveRepository

    iid = _resolve_incident_id(incident_id)
    repo = ApiObjectiveRepository(iid)
    detail = repo.create_objective(
        {
            "text": request_text,
            "priority": priority,
            "origin_module": "liaison",
            "origin_id": str(request_id),
        },
        user_id=user_id,
    )
    objective_id = detail.summary.id
    mark_agency_request_converted(request_id, "objective", objective_id, iid)
    return {"objective_id": objective_id}


def convert_agency_request_to_task(
    request_title: str,
    request_id: int,
    priority: str = "Medium",
    incident_id: object | None = None,
) -> dict[str, Any]:
    from modules.operations.taskings.repository import create_task

    iid = _resolve_incident_id(incident_id)
    task_int_id = create_task(
        title=request_title,
        priority=priority,
        origin_module="liaison",
        origin_id=str(request_id),
    )
    mark_agency_request_converted(request_id, "task", str(task_int_id), iid)
    return {"task_id": task_int_id}
