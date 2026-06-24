"""Generic IncidentCache snapshot + live-update WebSocket endpoint.

Serves every collection in `IncidentCollections` for a given incident, so the
desktop IncidentCache can bulk-load on incident open and then stay current via
the WebSocket without any per-module wiring. New collections show up here
automatically as they're added to IncidentCollections.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from sarapp_db.api.ws_hub import hub
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db

router = APIRouter()

_ALL_COLLECTIONS: List[str] = sorted(
    {
        value
        for name, value in vars(IncidentCollections).items()
        if not name.startswith("_") and isinstance(value, str)
    }
)


@router.get("/incidents/{incident_id}/snapshot")
def get_snapshot(
    incident_id: str,
    collections: Optional[str] = Query(default=None, description="Comma-separated collection names; omit for all"),
) -> Dict[str, Any]:
    """Return current documents for the requested collections (default: all)."""
    db = get_incident_db(incident_id)
    names = collections.split(",") if collections else _ALL_COLLECTIONS
    snapshot: Dict[str, List[Dict[str, Any]]] = {}
    for name in names:
        name = name.strip()
        if not name:
            continue
        snapshot[name] = list(db[name].find({"deleted": False}))
    return {"incident_id": incident_id, "collections": snapshot}


@router.websocket("/incidents/{incident_id}/ws")
async def incident_ws(websocket: WebSocket, incident_id: str) -> None:
    await hub.connect(incident_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(incident_id, websocket)
