"""Background WebSocket connector feeding IncidentCache live updates.

Connects to /api/incidents/{incident_id}/ws on the active SARApp server and
forwards every parsed JSON message into IncidentCache.apply_event(). Runs on
its own QThread so the GUI thread never blocks on socket I/O; reconnects with
a fixed backoff if the connection drops (server restart, network blip).
"""

from __future__ import annotations

import json
import logging
import time

from PySide6.QtCore import QThread

from utils.incident_cache import incident_cache

logger = logging.getLogger(__name__)

_RECONNECT_DELAY_SECONDS = 3


def _to_ws_url(http_base_url: str, incident_id: str) -> str:
    ws_base = http_base_url.replace("https://", "wss://").replace("http://", "ws://")
    return f"{ws_base.rstrip('/')}/api/incidents/{incident_id}/ws"


class IncidentWebSocketClient(QThread):
    """One instance per active incident. Call stop() before discarding."""

    def __init__(self, base_url: str, incident_id: str) -> None:
        super().__init__()
        self._url = _to_ws_url(base_url, incident_id)
        self._incident_id = incident_id
        self._stop_requested = False

    def stop(self) -> None:
        self._stop_requested = True
        self.requestInterruption()
        self.wait(2000)

    def run(self) -> None:
        import websocket  # websocket-client; imported lazily so headless/test envs don't need it

        while not self._stop_requested:
            try:
                ws = websocket.create_connection(self._url, timeout=10)
            except Exception as exc:
                logger.warning("IncidentCache WS connect failed (%s): %s", self._url, exc)
                time.sleep(_RECONNECT_DELAY_SECONDS)
                continue

            logger.info("IncidentCache WS connected for incident '%s'.", self._incident_id)
            # create_connection's timeout also governs recv(); idle gaps longer than it
            # would otherwise look like a dropped connection, so poll with short recv
            # timeouts and only treat real socket errors as a drop.
            ws.settimeout(1.0)
            try:
                while not self._stop_requested:
                    try:
                        raw = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue
                    if not raw:
                        break
                    try:
                        event = json.loads(raw)
                    except ValueError:
                        logger.warning("Ignoring non-JSON IncidentCache WS message: %r", raw)
                        continue
                    if event.get("type") == "notification":
                        from notifications.services.incident_bridge import handle_notification_event
                        handle_notification_event(self._incident_id, event.get("notification", {}))
                    else:
                        incident_cache.apply_event(event)
            except Exception as exc:
                if not self._stop_requested:
                    logger.warning("IncidentCache WS dropped (%s): %s", self._url, exc)
            finally:
                try:
                    ws.close()
                except Exception:
                    pass

            if not self._stop_requested:
                time.sleep(_RECONNECT_DELAY_SECONDS)
