from .repository import (
    create_agency,
    create_feedback,
    create_interaction,
    fetch_agency_detail,
    fetch_agency_rows,
    fetch_feedback_for_objective,
    fetch_feedback_for_resource_request,
    fetch_feedback_for_strategy,
    fetch_feedback_for_task,
    fetch_feedback_rows,
    update_agency_status,
)


def get_agencies_panel(incident_id: object | None = None):
    from .windows import get_agencies_panel as _get_agencies_panel

    return _get_agencies_panel(incident_id)


def get_requests_panel(incident_id: object | None = None):
    from .windows import get_requests_panel as _get_requests_panel

    return _get_requests_panel(incident_id)


__all__ = [
    "get_agencies_panel",
    "get_requests_panel",
    "create_agency",
    "create_feedback",
    "create_interaction",
    "fetch_agency_detail",
    "fetch_agency_rows",
    "fetch_feedback_rows",
    "fetch_feedback_for_objective",
    "fetch_feedback_for_strategy",
    "fetch_feedback_for_task",
    "fetch_feedback_for_resource_request",
    "update_agency_status",
]
