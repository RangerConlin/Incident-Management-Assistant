"""Background loop that evaluates due Planned Events schedule triggers.

Owned/started/stopped by `SARAppServerManager` the same way as
`DiscoveryBroadcaster`/`CloudTunnelClient` — a daemon thread, not a FastAPI
lifespan hook, since `create_app()` is shared across LAN/cloud/offline
server types and has no lifespan wiring today.

Runs identically whether this process is a LAN server, an offline
single-user server, or the local LAN server a cloud-connected incident dials
out from — all three are the same `SARAppServerManager` instance, so this
loop covers all of them without any deployment-mode branching.
"""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL_SECONDS = 30.0


class NotificationTriggerLoop:
    """Periodically evaluates due schedule triggers and emits notifications."""

    def __init__(self, *, interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS) -> None:
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="sarapp-notification-trigger-loop",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def _run(self) -> None:
        # Imported lazily so importing this module doesn't require the full
        # sarapp_db package graph unless the loop actually starts.
        from sarapp_db.services.trigger_engine import evaluate_all_incidents

        while not self._stop_event.is_set():
            try:
                evaluate_all_incidents()
            except Exception:
                logger.exception("Notification trigger loop tick failed.")
            self._stop_event.wait(self.interval_seconds)
