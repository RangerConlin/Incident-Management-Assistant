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


def get_reporting_panel(incident_id: object | None = None):
    from .panels.reporting_board import get_reporting_panel as _get_reporting_panel

    return _get_reporting_panel(incident_id)


def get_customer_panel(incident_id: object | None = None):
    from .panels.customer_board import get_customer_panel as _get_customer_panel

    return _get_customer_panel(incident_id)


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
        _liaison_window.switch_to_section(tab)
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
    "get_reporting_panel",
    "get_customer_panel",
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
