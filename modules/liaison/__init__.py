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


def get_agency_directory_panel(incident_id: object | None = None):
    from .panels.agency_directory_panel import get_agency_directory_panel as _get_agency_directory_panel

    return _get_agency_directory_panel(incident_id)


def get_agency_status_panel(incident_id: object | None = None):
    from .panels.agency_status_panel import get_agency_status_panel as _get_agency_status_panel

    return _get_agency_status_panel(incident_id)


def get_contacts_panel(incident_id: object | None = None):
    from .panels.contacts_panel import get_contacts_panel as _get_contacts_panel

    return _get_contacts_panel(incident_id)


def get_agreements_panel(incident_id: object | None = None):
    from .panels.agreements_panel import get_agreements_panel as _get_agreements_panel

    return _get_agreements_panel(incident_id)


def get_liaison_log_panel(incident_id: object | None = None):
    from .panels.liaison_log_panel import get_liaison_log_panel as _get_liaison_log_panel

    return _get_liaison_log_panel(incident_id)


def get_reporting_panel(incident_id: object | None = None):
    from .panels.reporting_board import get_reporting_panel as _get_reporting_panel

    return _get_reporting_panel(incident_id)


def get_customer_panel(incident_id: object | None = None):
    from .panels.customer_board import get_customer_panel as _get_customer_panel

    return _get_customer_panel(incident_id)


def get_requests_panel(incident_id: object | None = None):
    from .panels.requests_board import get_requests_panel as _get_requests_panel

    return _get_requests_panel(incident_id)


_liaison_window = None


def open_liaison_window(incident_id: object | None = None, tab: str | None = None, parent=None) -> None:
    """Open (or raise) the standalone Liaison dashboard, or a specific section window.

    If *tab* is given, opens only that section's window directly — the dashboard
    is not opened or raised.
    """
    global _liaison_window
    from .liaison_window import LiaisonWindow

    if tab:
        try:
            alive = _liaison_window is not None
        except RuntimeError:
            alive = False
            _liaison_window = None
        if not alive:
            _liaison_window = LiaisonWindow(incident_id, parent)
        elif getattr(_liaison_window, "_incident_id", None) != incident_id:
            _liaison_window.load_incident(incident_id)
        _liaison_window.switch_to_section(tab)
        _liaison_window.show()
        _liaison_window.raise_()
        _liaison_window.activateWindow()
        return

    try:
        alive = _liaison_window is not None and _liaison_window.isVisible()
    except RuntimeError:
        alive = False
        _liaison_window = None

    if not alive:
        _liaison_window = LiaisonWindow(incident_id, parent)
        _liaison_window.show()
    elif getattr(_liaison_window, "_incident_id", None) != incident_id:
        _liaison_window.load_incident(incident_id)
        _liaison_window.raise_()
        _liaison_window.activateWindow()
    else:
        _liaison_window.raise_()
        _liaison_window.activateWindow()


__all__ = [
    "get_agencies_panel",
    "get_agency_directory_panel",
    "get_agency_status_panel",
    "get_contacts_panel",
    "get_agreements_panel",
    "get_liaison_log_panel",
    "get_reporting_panel",
    "get_customer_panel",
    "get_requests_panel",
    "open_liaison_window",
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
