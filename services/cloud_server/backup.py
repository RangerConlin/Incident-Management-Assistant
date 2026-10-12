"""MongoDB backup import/export helpers for the hosted dashboard."""

from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bson import json_util
from pymongo import MongoClient

from sarapp_db.mongo.database_manager import DB_INCIDENT_PREFIX, DB_MASTER, DB_SYSTEM
from sarapp_db.mongo.mongo_client import get_mongo_uri

_BACKUP_VERSION = 1
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_-]+")


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _clean_label(value: str) -> str:
    cleaned = _SAFE_NAME.sub("-", value.strip()).strip("-")
    return cleaned or "import"


def _database_names(client: MongoClient) -> list[str]:
    names = [DB_SYSTEM, DB_MASTER]
    names.extend(sorted(n for n in client.list_database_names() if n.startswith(DB_INCIDENT_PREFIX)))
    return names


def export_backup(*, server_id: str, connect_code: str) -> tuple[str, bytes]:
    client = MongoClient(get_mongo_uri())
    exported_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db_names = _database_names(client)
    metadata: dict[str, Any] = {
        "format": "sarapp-mongo-backup",
        "version": _BACKUP_VERSION,
        "exported_at": exported_at,
        "server_id": server_id,
        "connect_code": connect_code,
        "databases": db_names,
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("metadata.json", json.dumps(metadata, indent=2, sort_keys=True))
        for db_name in db_names:
            db = client[db_name]
            collection_names = sorted(db.list_collection_names())
            archive.writestr(
                f"databases/{db_name}/collections.json",
                json.dumps(collection_names, indent=2),
            )
            for collection_name in collection_names:
                docs = list(db[collection_name].find({}))
                archive.writestr(
                    f"databases/{db_name}/{collection_name}.json",
                    json_util.dumps(docs, indent=2),
                )
    filename = f"sarapp-backup-{_clean_label(connect_code)}-{_utc_stamp()}.zip"
    return filename, buffer.getvalue()


def save_uploaded_backup(data: bytes, backup_dir: str, filename: str) -> Path:
    target_dir = Path(backup_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename).name or f"uploaded-{_utc_stamp()}.zip"
    target = target_dir / safe_name
    target.write_bytes(data)
    return target


def list_backups(backup_dir: str) -> list[dict[str, Any]]:
    root = Path(backup_dir)
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True):
        stat = path.stat()
        rows.append(
            {
                "name": path.name,
                "size": stat.st_size,
                "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(
                    timespec="seconds"
                ),
            }
        )
    return rows


def import_backup(data: bytes, *, label: str) -> dict[str, Any]:
    suffix = _clean_label(label or f"import-{_utc_stamp()}")
    client = MongoClient(get_mongo_uri())
    restored: list[dict[str, Any]] = []
    with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
        metadata = json.loads(archive.read("metadata.json").decode("utf-8"))
        if metadata.get("format") != "sarapp-mongo-backup":
            raise ValueError("Unsupported SARApp backup format")
        for source_db in metadata.get("databases", []):
            collections_path = f"databases/{source_db}/collections.json"
            collection_names = json.loads(archive.read(collections_path).decode("utf-8"))
            target_db_name = f"{source_db}_{suffix}"
            target_db = client[target_db_name]
            for collection_name in collection_names:
                raw = archive.read(f"databases/{source_db}/{collection_name}.json").decode("utf-8")
                docs = json_util.loads(raw)
                if docs:
                    target_db[collection_name].insert_many(docs)
                else:
                    target_db.create_collection(collection_name)
            restored.append({"source": source_db, "target": target_db_name})
    return {"restored": restored}

