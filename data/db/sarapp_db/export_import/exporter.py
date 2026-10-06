"""Build a universal incident export package (see package docstring)."""

from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import datetime, timezone
from typing import Any

import gridfs
from bson import json_util

from sarapp_db.mongo.collection_names import IncidentCollections, SystemCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_system_db
from sarapp_db.mongo.errors import RepositoryError
from sarapp_db.mongo.repository import BaseRepository

FORMAT_ID = "sarapp-incident-export"
FORMAT_VERSION = 1

_GRIDFS_COLLECTION = "attachment_files"
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_-]+")

# Every incident-scoped collection name, deduped (IncidentCollections has a
# couple of aliases, e.g. OPERATIONS_TASKS == TASKS, that point at the same
# underlying collection).
_INCIDENT_COLLECTION_NAMES: list[str] = sorted(
    {
        value
        for name, value in vars(IncidentCollections).items()
        if not name.startswith("_") and isinstance(value, str)
    }
)


class _SystemIncidentsRepository(BaseRepository):
    collection_name = SystemCollections.INCIDENTS
    soft_deletes = False


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _clean_label(value: str) -> str:
    cleaned = _SAFE_NAME.sub("-", value.strip()).strip("-")
    return cleaned or "incident"


def build_incident_export(incident_id: str) -> tuple[str, bytes]:
    """Return (filename, zip bytes) for a full export of one incident."""
    registry = _SystemIncidentsRepository(get_system_db()).find_one({"incident_id": incident_id})
    if registry is None:
        raise RepositoryError(f"Incident '{incident_id}' not found")

    db = get_incident_db(incident_id)
    exported_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    manifest: dict[str, Any] = {
        "format": FORMAT_ID,
        "version": FORMAT_VERSION,
        "exported_at": exported_at,
        "source": {
            "incident_id": incident_id,
            "number": registry.get("number", ""),
            "name": registry.get("name", ""),
            "type": registry.get("type", ""),
        },
        "collections": [],
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for collection_name in _INCIDENT_COLLECTION_NAMES:
            docs = list(db[collection_name].find({}))
            if not docs:
                continue
            manifest["collections"].append(collection_name)
            archive.writestr(
                f"collections/{collection_name}.json",
                json_util.dumps(docs, indent=2),
            )

        fs = gridfs.GridFS(db, collection=_GRIDFS_COLLECTION)
        attachments_manifest: list[dict[str, Any]] = []
        for grid_out in fs.find():
            file_id = str(grid_out._id)
            attachments_manifest.append(
                {
                    "old_file_id": file_id,
                    "filename": grid_out.filename,
                    # Read straight off the underlying files-collection doc
                    # rather than GridOut.content_type, which pymongo has
                    # deprecated in favor of this.
                    "content_type": grid_out._file.get("contentType"),
                    "length": grid_out.length,
                    "metadata": grid_out.metadata or {},
                }
            )
            archive.writestr(f"attachments/{file_id}.bin", grid_out.read())
        archive.writestr("attachments/manifest.json", json.dumps(attachments_manifest, indent=2))

        # manifest.json last so attachments_manifest above is reflected, but
        # keep it as the only top-level entry for easy peeking.
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))

    filename = (
        f"incident-{_clean_label(registry.get('number') or incident_id)}-{_utc_stamp()}.zip"
    )
    return filename, buffer.getvalue()
