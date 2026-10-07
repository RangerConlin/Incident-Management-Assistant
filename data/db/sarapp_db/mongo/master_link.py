"""The `master_link` sub-document: ties an incident-local record back to the
master-catalog record it was copied from.

See Design Documents/Instructions/mongodb_schema_decisions.md ("Master-
Incident Record Linking") for the full design. Embedded as a top-level
`master_link` field on incident-scoped documents that copy fields from a
master-catalog record (e.g. `incident_personnel` <- `MasterCollections.
PERSONNEL`) — not a separate join collection, matching this repo's existing
preference for embedding 1:1 pointers over new link tables.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

# sync_state values
LINKED = "linked"
CONFLICT = "conflict"
ORPHANED = "orphaned"
LOCAL_ONLY = "local_only"

_VALID_SYNC_STATES = {LINKED, CONFLICT, ORPHANED, LOCAL_ONLY}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_master_link(
    *,
    master_collection: str,
    master_server_origin: str,
    master_id: Optional[str] = None,
    central_master_id: Optional[str] = None,
    sync_state: str = LINKED,
) -> dict[str, Any]:
    """Build a fresh `master_link` sub-document for a newly-copied record.

    Called at the moment an incident-local record is first populated from a
    master-catalog record (e.g. the check-in roster mirroring a master
    personnel record into `incident_personnel`), or by a one-time backfill
    migration reconstructing links for pre-existing data. `master_id` may be
    omitted only for `sync_state="orphaned"` — a record known to have come
    from a master collection but whose specific master record can no longer
    be identified (e.g. the weak legacy reference didn't resolve to anything
    during a backfill).
    """
    if sync_state not in _VALID_SYNC_STATES:
        raise ValueError(f"Unknown master_link sync_state: {sync_state!r}")
    if master_id is None and sync_state != ORPHANED:
        raise ValueError("master_id is required unless sync_state is 'orphaned'")
    return {
        "master_collection": master_collection,
        "master_id": master_id,
        "master_server_origin": master_server_origin,
        "central_master_id": central_master_id,
        "last_synced_at": _utcnow_iso(),
        "sync_state": sync_state,
        "conflict": None,
    }


def mark_orphaned(master_link: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of `master_link` with sync_state set to "orphaned".

    Used when a record's master reference can no longer be resolved on the
    server it now lives on (e.g. after import into a server with no matching
    local master record and no resolvable central_master_id).
    """
    updated = dict(master_link)
    updated["sync_state"] = ORPHANED
    return updated
