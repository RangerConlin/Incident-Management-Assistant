"""
Audit log writer for SARApp.

Writes structured audit records to the audit_logs collection of the active
incident database. Used by the SARApp server only.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo.database import Database

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.errors import AuditWriteError

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_audit(
    incident_db: Database,
    *,
    incident_id: str,
    entity_type: str,
    entity_id: str,
    action: str,
    changed_by: str,
    field_changes: Optional[List[Dict[str, Any]]] = None,
    source_module: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Write a single audit record to the incident's audit_logs collection.

    Raises AuditWriteError on failure.
    """
    record: Dict[str, Any] = {
        "_id": str(uuid.uuid4()),
        "incident_id": incident_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action": action,
        "changed_by": changed_by,
        "field_changes": field_changes or [],
        "source_module": source_module or "",
        "timestamp": timestamp or _utcnow_iso(),
    }
    try:
        incident_db[IncidentCollections.AUDIT_LOGS].insert_one(record)
    except Exception as exc:
        raise AuditWriteError(
            f"Failed to write audit record for {entity_type}/{entity_id}: {exc}"
        ) from exc
    logger.debug("Audit: %s %s/%s by %s", action, entity_type, entity_id, changed_by)
    return record


def write_audit_bulk(incident_db: Database, records: List[Dict[str, Any]]) -> None:
    """
    Insert multiple pre-built audit records in one operation.

    Raises AuditWriteError on failure.
    """
    if not records:
        return
    now = _utcnow_iso()
    docs = []
    for rec in records:
        doc = dict(rec)
        doc.setdefault("_id", str(uuid.uuid4()))
        doc.setdefault("timestamp", now)
        doc.setdefault("field_changes", [])
        doc.setdefault("source_module", "")
        docs.append(doc)
    try:
        incident_db[IncidentCollections.AUDIT_LOGS].insert_many(docs, ordered=False)
    except Exception as exc:
        raise AuditWriteError(f"Bulk audit write failed ({len(docs)} records): {exc}") from exc
