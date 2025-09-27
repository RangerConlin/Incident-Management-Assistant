"""Communications module exports."""


def create_ics205_window(parent=None):
    from .panels.ics205_window import ICS205Window

    return ICS205Window(parent)


def create_traffic_log_window(parent=None, *, incident_id=None):
    from .traffic_log import create_log_window

    return create_log_window(parent=parent, incident_id=incident_id)


def get_communications_log_service(*, incident_id=None):
    from .traffic_log import CommsLogService

    return CommsLogService(incident_id=incident_id)


__all__ = [
    "create_ics205_window",
    "create_traffic_log_window",
    "get_communications_log_service",
]
