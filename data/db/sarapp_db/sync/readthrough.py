"""Read-through helpers for central master-catalog data.

Desktop clients always read master data from their active LAN/cloud/offline
server. When that server is connected to the central catalog, selected master
read paths can pull central changes first, apply them locally, then serve the
request from the refreshed local catalog.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def refresh_collection_before_read(collection: str) -> None:
    """Best-effort central pull for a master collection before serving a read.

    This intentionally never raises: a temporarily unreachable cloud catalog
    must not break local/offline reads. The caller still reads from local
    MongoDB after this returns.
    """
    try:
        from sarapp_db.mongo.database_manager import get_master_db, is_central_master_db
        from sarapp_db.sync import config

        if not config.sync_enabled():
            return
        if is_central_master_db(get_master_db()):
            return
        if collection not in config.SYNCABLE_MASTER_COLLECTIONS:
            return

        from sarapp_db.sync.loop import pull_and_apply

        pull_and_apply(collection)
    except Exception:
        logger.exception("Central read-through refresh failed for %s", collection)
