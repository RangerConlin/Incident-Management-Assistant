"""Public Information module entry points."""
from __future__ import annotations

from typing import Any

from modules.public_information.services import PublicInformationRepository


def get_public_information_panel(
    incident_id: str | None = None,
    current_user: dict[str, Any] | None = None,
    parent=None,
):
    from modules.public_information.panels import PublicInformationDashboardPanel

    return PublicInformationDashboardPanel(incident_id, current_user, parent)


def get_public_info_panel(
    incident_id: str | None = None,
    current_user: dict[str, Any] | None = None,
    parent=None,
):
    return get_public_information_panel(incident_id, current_user, parent)


def get_media_releases_panel(incident_id: str | None = None, parent=None):
    from modules.public_information.panels.message_manager import MessageManagerPanel

    return MessageManagerPanel(PublicInformationRepository(incident_id), {}, parent)


def get_inquiries_panel(incident_id: str | None = None, parent=None):
    from modules.public_information.panels.simple_panels import MediaLogPanel

    return MediaLogPanel(PublicInformationRepository(incident_id), {}, parent)


__all__ = [
    "PublicInformationRepository",
    "get_public_information_panel",
    "get_public_info_panel",
    "get_media_releases_panel",
    "get_inquiries_panel",
]
