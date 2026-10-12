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

SNAPSHOT_MAX_MB = 150
SNAPSHOT_MAX_COLLECTION_DOCS = 5000
SNAPSHOT_MAX_HEAVY_COLLECTION_DOCS = 500


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
        snapshot = api_client.get(
            f"/api/incidents/{incident_id}/snapshot",
            params={
                "max_snapshot_mb": SNAPSHOT_MAX_MB,
                "max_collection_docs": SNAPSHOT_MAX_COLLECTION_DOCS,
                "max_heavy_collection_docs": SNAPSHOT_MAX_HEAVY_COLLECTION_DOCS,
            },
        )
    except APIError as exc:
        logger.warning("IncidentCache snapshot load failed for '%s': %s", incident_id, exc)
        incident_cache.clear()
        return

    incident_cache.load_snapshot(
        incident_id,
        snapshot.get("collections", {}),
        meta=snapshot.get("meta") or {},
    )
    telemetry = incident_cache.telemetry()
    logger.info(
        "IncidentCache active for '%s': %s docs, ~%s MB%s",
        incident_id,
        telemetry.get("total_docs", 0),
        telemetry.get("estimated_mb", 0.0),
        " (truncated)" if telemetry.get("snapshot_truncated") else "",
    )

    # Initialize the active operational period from the server so it is
    # known program-wide immediately after incident selection.
    try:
        op_data = api_client.get(
            f"/api/incidents/{incident_id}/planning/operational-periods/active"
        )
        if op_data:
            from utils.state import AppState
            AppState.set_active_op_period({
                "number": op_data.get("number"),
                "id": op_data.get("id"),
                "status": op_data.get("status", "Active"),
                "start_time": op_data.get("start_time", ""),
                "end_time": op_data.get("end_time", ""),
            })
            logger.debug(
                "Restored active OP %s for incident '%s'",
                op_data.get("number"), incident_id,
            )
    except Exception as exc:
        logger.debug(
            "No active operational period for incident '%s': %s",
            incident_id, exc,
        )

    _ws_client = IncidentWebSocketClient(api_client.base_url, incident_id)
    _ws_client.start()


def shutdown() -> None:
    """Stop the active incident websocket client and clear cached data."""
    global _ws_client

    if _ws_client is not None:
        _ws_client.stop()
        _ws_client = None
    incident_cache.clear()
