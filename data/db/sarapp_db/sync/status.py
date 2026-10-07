"""Human-readable snapshot of central-catalog sync state, for the LAN
console / cloud dashboard to display without each reaching into
`outbox`/`checkpoint` internals directly.
"""

from __future__ import annotations

from typing import Any


def get_sync_status() -> dict[str, Any]:
    """Return the current sync configuration and progress for this server.

    Safe to call whether or not sync is configured — `enabled=False` means
    `SARAPP_CENTRAL_MASTER_URL` isn't set, and every other field is empty
    rather than attempting a Mongo read that has nothing meaningful to find.
    """
    from sarapp_db.mongo.database_manager import get_system_db
    from sarapp_db.sync import checkpoint, config, outbox

    enabled = config.sync_enabled()
    if not enabled:
        return {
            "enabled": False,
            "central_master_url": "",
            "pending_count": 0,
            "last_pulled": {},
        }

    system_db = get_system_db()
    last_pulled = {
        collection: checkpoint.get_last_pulled_at(system_db, collection)
        for collection in config.SYNCABLE_MASTER_COLLECTIONS
    }
    return {
        "enabled": True,
        "central_master_url": config.central_master_url(),
        "pending_count": len(outbox.list_pending(system_db)),
        "last_pulled": last_pulled,
    }
