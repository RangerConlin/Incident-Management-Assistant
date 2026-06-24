"""Client-side in-memory cache of the active incident's MongoDB collections.

Populated from a server snapshot on incident load, then kept current by
change events pushed over the IncidentCache WebSocket
(see utils/incident_ws_client.py). All panels should read from this cache
instead of issuing their own GET requests for incident data; writes still go
through the existing module REST endpoints — the server broadcasts the
resulting change back out to every connected client, including the writer.

Usage:
    from utils.incident_cache import incident_cache

    teams = incident_cache.get_all("teams")
    team = incident_cache.get("teams", team_id)
    incident_cache.changed.connect(my_slot)  # (collection, op, doc_id)
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class IncidentCache(QObject):
    """Generic collection-name-keyed store. One instance, scoped to the active incident."""

    # (collection, op, doc_id) — op is "created" | "updated" | "deleted"
    changed = Signal(str, str, str)
    # Emitted after load_snapshot() replaces the whole cache (e.g. on incident switch)
    snapshotLoaded = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._store: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._incident_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Bulk load / clear
    # ------------------------------------------------------------------

    def load_snapshot(self, incident_id: str, collections: Dict[str, List[Dict[str, Any]]]) -> None:
        """Replace the entire cache with a fresh snapshot from the server."""
        with self._lock:
            self._incident_id = incident_id
            self._store = {
                name: {str(doc["_id"]): doc for doc in docs}
                for name, docs in collections.items()
            }
        logger.info("IncidentCache snapshot loaded for incident '%s' (%d collections).", incident_id, len(collections))
        self.snapshotLoaded.emit()

    def clear(self) -> None:
        with self._lock:
            self._incident_id = None
            self._store = {}
        self.snapshotLoaded.emit()

    @property
    def incident_id(self) -> Optional[str]:
        return self._incident_id

    # ------------------------------------------------------------------
    # Live event application
    # ------------------------------------------------------------------

    def apply_event(self, event: Dict[str, Any]) -> None:
        """Apply one {collection, op, id, doc} change event. Thread-safe.

        Safe to call from a background WebSocket thread — Qt marshals the
        `changed` signal to the main thread automatically because slots
        connected from the GUI thread use a queued connection by default
        across threads.
        """
        collection = event.get("collection")
        op = event.get("op")
        doc_id = event.get("id")
        doc = event.get("doc")
        if not collection or not op or doc_id is None:
            logger.warning("Ignoring malformed IncidentCache event: %s", event)
            return

        with self._lock:
            bucket = self._store.setdefault(collection, {})
            if op == "deleted":
                bucket.pop(doc_id, None)
            elif doc is not None:
                bucket[doc_id] = doc

        self.changed.emit(collection, op, doc_id)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get(self, collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._store.get(collection, {}).get(doc_id)

    def get_all(self, collection: str) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._store.get(collection, {}).values())

    def query(self, collection: str, predicate: Callable[[Dict[str, Any]], bool]) -> List[Dict[str, Any]]:
        with self._lock:
            docs = list(self._store.get(collection, {}).values())
        return [d for d in docs if predicate(d)]


# Module-level singleton — import and use directly.
incident_cache = IncidentCache()

__all__ = ["incident_cache", "IncidentCache"]
