"""Generic per-incident WebSocket hub for IncidentCache change broadcasts.

One hub serves every collection for a given incident_id — there is no
per-collection or per-module wiring. `sarapp_db.mongo.repository.BaseRepository`
calls `broadcast_change` itself after every insert/update, so module
repositories built on top of it get broadcasting for free.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Dict, List

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class IncidentWebSocketHub:
    def __init__(self) -> None:
        self._connections: Dict[str, List[WebSocket]] = defaultdict(list)
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, incident_id: str, websocket: WebSocket) -> None:
        # The running server has exactly one event loop for its whole
        # lifetime; capture it here so broadcast() can schedule sends from any
        # thread (FastAPI runs sync route handlers, and therefore repository
        # writes, in a worker thread, not this loop). Refreshed on every
        # connect rather than cached once so test suites that spin up a fresh
        # event loop per test (one app/loop per TestClient) stay correct too.
        self._loop = asyncio.get_running_loop()
        await websocket.accept()
        self._connections[incident_id].append(websocket)

    def disconnect(self, incident_id: str, websocket: WebSocket) -> None:
        conns = self._connections.get(incident_id)
        if conns and websocket in conns:
            conns.remove(websocket)

    def broadcast(self, incident_id: str, event: Dict[str, Any]) -> None:
        """Fan out an event to every client connected for this incident.

        Safe to call from synchronous repository code running in any thread —
        schedules the actual send onto the captured event loop. No-ops if no
        client has ever connected yet (loop not captured) or none are
        currently connected for this incident.
        """
        conns = self._connections.get(incident_id)
        if not conns or self._loop is None:
            return
        for ws in list(conns):
            asyncio.run_coroutine_threadsafe(self._safe_send(incident_id, ws, event), self._loop)

    async def _safe_send(self, incident_id: str, ws: WebSocket, event: Dict[str, Any]) -> None:
        try:
            await ws.send_json(event)
        except Exception:
            self.disconnect(incident_id, ws)


hub = IncidentWebSocketHub()


def broadcast_change(incident_id: str, collection: str, op: str, doc_id: str, doc: Dict[str, Any] | None) -> None:
    """Broadcast a single collection change to all clients watching this incident.

    op is one of "created", "updated", "deleted".
    """
    hub.broadcast(incident_id, {"collection": collection, "op": op, "id": doc_id, "doc": doc})
