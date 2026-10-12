"""Restore a universal incident export package as a brand-new incident."""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

import gridfs
from bson import ObjectId, json_util

from sarapp_db.api.routers.ic_overview import CreateIncidentRequest, create_incident_records
from sarapp_db.export_import.exporter import FORMAT_ID, FORMAT_VERSION, _GRIDFS_COLLECTION
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import DatabaseManager, get_incident_db, get_master_db
from sarapp_db.mongo.master_link import mark_orphaned
from sarapp_db.mongo.repository import BaseRepository
from sarapp_db.mongo.server_identity import get_server_id


class ImportFormatError(ValueError):
    """Raised when the uploaded file isn't a recognized incident export."""


def _repo_for(db, collection_name: str) -> BaseRepository:
    cls = type("_ImportRepository", (BaseRepository,), {"collection_name": collection_name})
    return cls(db)


def _resolve_master_link(doc: dict[str, Any], *, this_server_id: str) -> None:
    """Re-resolve `doc["master_link"]` against this server's own master DB.

    A document's `master_id` only means something on the server it was
    originally copied from — importing it elsewhere can't assume that same
    UUID exists in this server's independent local master catalog. Mark the
    link `orphaned` rather than silently keeping a dangling foreign id,
    unless the record demonstrably still resolves locally (it was exported
    from, and is being imported back into, this same server).
    """
    link = doc.get("master_link")
    if not link:
        return

    if link.get("master_server_origin") == this_server_id:
        found = get_master_db()[link["master_collection"]].find_one({"_id": link["master_id"]})
        if found is not None:
            return  # Still resolves locally — leave the link as-is.

    # Foreign origin, or same origin but the master record is gone: no
    # central_master_id resolution path exists yet (that lands with the
    # change-stream sync relay — see realtime_architecture_roadmap.md), so
    # there is nothing left to try.
    doc["master_link"] = mark_orphaned(link)


def _resolve_master_links_for_collection(docs: list[dict[str, Any]]) -> None:
    this_server_id = get_server_id()
    for doc in docs:
        _resolve_master_link(doc, this_server_id=this_server_id)


def import_incident_export(data: bytes, *, number: str, name: str) -> dict[str, Any]:
    """Create a new incident from an exported package and restore its data.

    `number`/`name` are the (possibly user-edited) identifiers for the new
    incident on this server — kept separate from whatever the source
    incident was called, so importing never collides with an existing
    incident number here.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(data), "r")
    except zipfile.BadZipFile as exc:
        raise ImportFormatError("File is not a valid incident export (not a zip archive)") from exc

    with archive:
        try:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        except KeyError as exc:
            raise ImportFormatError("File is not a valid incident export (missing manifest.json)") from exc
        if manifest.get("format") != FORMAT_ID:
            raise ImportFormatError("File is not a SARApp incident export")
        if manifest.get("version") != FORMAT_VERSION:
            raise ImportFormatError(f"Unsupported incident export version: {manifest.get('version')!r}")

        source = manifest.get("source", {})
        body = CreateIncidentRequest(
            number=number,
            name=name,
            type=source.get("type", ""),
        )
        registry_doc = create_incident_records(body)
        incident_id = registry_doc["id"]
        db = get_incident_db(incident_id)

        # Restore GridFS attachment bytes first so we have an old->new file
        # id map before restoring the `attachments` metadata collection.
        file_id_map: dict[str, str] = {}
        try:
            attachments_manifest = json.loads(archive.read("attachments/manifest.json").decode("utf-8"))
        except KeyError:
            attachments_manifest = []
        if attachments_manifest:
            fs = gridfs.GridFS(db, collection=_GRIDFS_COLLECTION)
            for entry in attachments_manifest:
                old_file_id = entry["old_file_id"]
                blob = archive.read(f"attachments/{old_file_id}.bin")
                metadata = dict(entry.get("metadata") or {})
                if "incident_id" in metadata:
                    metadata["incident_id"] = incident_id
                new_file_id = fs.put(
                    blob,
                    filename=entry.get("filename"),
                    content_type=entry.get("content_type"),
                    metadata=metadata,
                )
                file_id_map[old_file_id] = str(new_file_id)

        for collection_name in manifest.get("collections", []):
            raw = archive.read(f"collections/{collection_name}.json").decode("utf-8")
            docs = json_util.loads(raw)
            if not docs:
                continue
            for doc in docs:
                # Many collections embed the owning incident_id redundantly
                # alongside living in that incident's own database (used for
                # query filters throughout the routers) — it has to follow
                # the new incident, not stay pointed at the source one.
                if "incident_id" in doc:
                    doc["incident_id"] = incident_id
                if collection_name == IncidentCollections.ATTACHMENTS:
                    old_gridfs_id = doc.get("gridfs_file_id")
                    if old_gridfs_id is not None and str(old_gridfs_id) in file_id_map:
                        doc["gridfs_file_id"] = ObjectId(file_id_map[str(old_gridfs_id)])
            _resolve_master_links_for_collection(docs)
            _repo_for(db, collection_name).bulk_insert(docs)

    DatabaseManager().create_indexes(incident_id)
    return registry_doc
