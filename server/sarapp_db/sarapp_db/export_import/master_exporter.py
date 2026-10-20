"""Build a zip export of every master-catalog collection (see package docstring)."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any

from bson import json_util

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.server_identity import get_server_id

FORMAT_ID = "sarapp-master-export"
FORMAT_VERSION = 1

# Collections deliberately left out of the export: account credentials,
# sessions, device tokens, and internal sync/audit bookkeeping are not
# "catalog" data and shouldn't leave the server in a downloadable file.
_EXCLUDED_COLLECTIONS = {
    MasterCollections.USERS,
    MasterCollections.USER_SESSIONS,
    MasterCollections.USER_PROFILES,
    MasterCollections.ROLE_TEMPLATES,
    MasterCollections.CLIENT_CONNECTIONS,
    MasterCollections.PUSH_TOKENS,
    MasterCollections.ORGANIZATION_AUDIT_LOG,
    MasterCollections.RANK_STRUCTURE_AUDIT_LOG,
    MasterCollections.EMS_AGENCY_AUDIT_LOG,
}

# Every master catalog collection name, deduped, minus the exclusions above.
# Derived from the MasterCollections constants (not the central-master GUI's
# CollectionSpec registry) so a newly added master collection is picked up
# automatically without touching this file.
_MASTER_COLLECTION_NAMES: list[str] = sorted(
    {
        value
        for name, value in vars(MasterCollections).items()
        if not name.startswith("_") and isinstance(value, str)
    }
    - _EXCLUDED_COLLECTIONS
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_master_export() -> tuple[str, bytes]:
    """Return (filename, zip bytes) for a full export of every master-catalog collection."""
    db = get_master_db()
    exported_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    manifest: dict[str, Any] = {
        "format": FORMAT_ID,
        "version": FORMAT_VERSION,
        "exported_at": exported_at,
        "server_id": get_server_id(),
        "collections": [],
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for collection_name in _MASTER_COLLECTION_NAMES:
            docs = list(db[collection_name].find({}))
            if not docs:
                continue
            manifest["collections"].append(collection_name)
            archive.writestr(
                f"collections/{collection_name}.json",
                json_util.dumps(docs, indent=2),
            )

        archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))

    filename = f"master-catalog-export-{_utc_stamp()}.zip"
    return filename, buffer.getvalue()
