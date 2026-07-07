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

import json
import logging
import threading
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

DEFAULT_MAX_COLLECTION_DOCS = 5000
DEFAULT_MAX_HEAVY_COLLECTION_DOCS = 500

HEAVY_COLLECTIONS = {
    "attachments",
    "audit_logs",
    "checkin_history",
    "communications_log",
    "comms_log_audit",
    "form_instance_audit",
    "form_instance_exports",
    "form_instance_revisions",
    "ics_214_logs",
    "incident_journal",
    "intel_log",
    "notifications",
    "pio_distribution_log",
    "pio_generated_documents",
    "pio_message_revisions",
    "pio_misinformation_timeline",
    "task_narratives",
    "unit_logs",
}


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
        self._incident: Optional[Dict[str, Any]] = None
        self._snapshot_meta: Dict[str, Any] = {}
        self._policy: Dict[str, Any] = {
            "max_collection_docs": DEFAULT_MAX_COLLECTION_DOCS,
            "max_heavy_collection_docs": DEFAULT_MAX_HEAVY_COLLECTION_DOCS,
            "heavy_collections": sorted(HEAVY_COLLECTIONS),
        }

    # ------------------------------------------------------------------
    # Bulk load / clear
    # ------------------------------------------------------------------

    def load_snapshot(
        self,
        incident_id: str,
        collections: Dict[str, List[Dict[str, Any]]],
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Replace the entire cache with a fresh snapshot from the server."""
        normalized_incident = self._normalize_incident_from_collections(incident_id, collections)
        meta = dict(meta or {})
        policy = dict(meta.get("policy") or {})
        with self._lock:
            self._incident_id = incident_id
            self._incident = normalized_incident
            self._snapshot_meta = meta
            if policy:
                self._policy.update(policy)
            self._store = {
                name: {str(doc.get("_id")): doc for doc in docs if doc.get("_id") is not None}
                for name, docs in collections.items()
            }
            self._trim_all_locked()
        logger.info(
            "IncidentCache snapshot loaded for incident '%s' (%d collections, %.2f MB estimated).",
            incident_id,
            len(collections),
            self.telemetry().get("estimated_mb", 0.0),
        )
        self.snapshotLoaded.emit()

    def clear(self) -> None:
        with self._lock:
            self._incident_id = None
            self._incident = None
            self._store = {}
            self._snapshot_meta = {}
        self.snapshotLoaded.emit()

    @property
    def incident_id(self) -> Optional[str]:
        return self._incident_id

    def active_incident(self) -> Optional[Dict[str, Any]]:
        """Return normalized metadata for the active incident, if loaded."""
        with self._lock:
            return dict(self._incident) if self._incident else None

    def set_active_incident(self, incident: Optional[Dict[str, Any]]) -> None:
        """Set normalized active incident metadata without replacing collections."""
        with self._lock:
            self._incident = self._normalize_incident(incident) if incident else None

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
                self._trim_collection_locked(collection)
                if collection == "incident_profile":
                    self._incident = self._normalize_incident(doc, fallback_id=self._incident_id)

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

    def snapshot_meta(self) -> Dict[str, Any]:
        """Return server metadata describing snapshot caps and truncation."""
        with self._lock:
            return dict(self._snapshot_meta)

    def telemetry(self) -> Dict[str, Any]:
        """Return approximate cache size/count telemetry for diagnostics."""
        with self._lock:
            collections: Dict[str, Dict[str, Any]] = {}
            total_docs = 0
            total_bytes = 0
            for name, bucket in self._store.items():
                docs = list(bucket.values())
                count = len(docs)
                bytes_used = self._estimate_json_bytes(docs)
                total_docs += count
                total_bytes += bytes_used
                collections[name] = {
                    "docs": count,
                    "estimated_bytes": bytes_used,
                    "heavy": name in self._heavy_collections(),
                    "truncated": name in (self._snapshot_meta.get("truncated") or {}),
                }
            return {
                "incident_id": self._incident_id,
                "collections": collections,
                "total_docs": total_docs,
                "estimated_bytes": total_bytes,
                "estimated_mb": round(total_bytes / (1024 * 1024), 2),
                "snapshot_truncated": bool(self._snapshot_meta.get("truncated")),
                "snapshot_truncated_by_budget": bool(self._snapshot_meta.get("truncated_by_budget")),
            }

    def _trim_all_locked(self) -> None:
        for collection in list(self._store):
            self._trim_collection_locked(collection)

    def _trim_collection_locked(self, collection: str) -> None:
        bucket = self._store.get(collection)
        if not bucket:
            return
        limit = self._collection_limit(collection)
        overflow = len(bucket) - limit
        if overflow <= 0:
            return
        for key in list(bucket.keys())[:overflow]:
            bucket.pop(key, None)

    def _collection_limit(self, collection: str) -> int:
        if collection in self._heavy_collections():
            return int(self._policy.get("max_heavy_collection_docs") or DEFAULT_MAX_HEAVY_COLLECTION_DOCS)
        return int(self._policy.get("max_collection_docs") or DEFAULT_MAX_COLLECTION_DOCS)

    def _heavy_collections(self) -> set[str]:
        values = self._policy.get("heavy_collections") or HEAVY_COLLECTIONS
        return {str(value) for value in values}

    @staticmethod
    def _estimate_json_bytes(value: Any) -> int:
        try:
            return len(json.dumps(value, default=str, separators=(",", ":")).encode("utf-8"))
        except Exception:
            return 0

    def _normalize_incident_from_collections(
        self,
        incident_id: str,
        collections: Dict[str, List[Dict[str, Any]]],
    ) -> Optional[Dict[str, Any]]:
        profiles = collections.get("incident_profile") or []
        profile = next(
            (doc for doc in profiles if str(doc.get("incident_id") or "") == str(incident_id)),
            profiles[0] if profiles else None,
        )
        return self._normalize_incident(profile, fallback_id=incident_id)

    @staticmethod
    def _normalize_incident(
        incident: Optional[Dict[str, Any]],
        *,
        fallback_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if not incident:
            return None
        incident_id = str(
            incident.get("incident_id")
            or incident.get("id")
            or fallback_id
            or ""
        )
        number = str(
            incident.get("number")
            or incident.get("incident_number")
            or incident_id
        )
        return {
            **incident,
            "id": incident_id,
            "incident_id": incident_id,
            "number": number,
            "name": str(incident.get("name") or ""),
            "type": str(incident.get("type") or incident.get("incident_type") or ""),
        }


# Module-level singleton — import and use directly.
incident_cache = IncidentCache()

__all__ = ["incident_cache", "IncidentCache"]
