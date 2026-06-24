"""Drives IncidentCache lifecycle: snapshot load + WebSocket connect/disconnect
on incident switch. Called from AppState.set_active_incident — not meant to be
called directly by panels.
"""

from __future__ import annotations

import logging
from typing import Optional

from utils.api_client import api_client, APIError
from utils.incident_cache import incident_cache
from utils.incident_ws_client import IncidentWebSocketClient

logger = logging.getLogger(__name__)

_ws_client: Optional[IncidentWebSocketClient] = None


def activate_incident(incident_id: Optional[str]) -> None:
    """Tear down the previous incident's cache/WS and bring up the new one."""
    global _ws_client

    if _ws_client is not None:
        _ws_client.stop()
        _ws_client = None

    if incident_id is None:
        incident_cache.clear()
        return

    try:
        snapshot = api_client.get(f"/api/incidents/{incident_id}/snapshot")
    except APIError as exc:
        logger.warning("IncidentCache snapshot load failed for '%s': %s", incident_id, exc)
        incident_cache.clear()
        return

    incident_cache.load_snapshot(incident_id, snapshot.get("collections", {}))

    _ws_client = IncidentWebSocketClient(api_client.base_url, incident_id)
    _ws_client.start()
