from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

FOLDER_VERSION = 1
_RESERVED_FILES = {"template.db", "incident_template.db"}
_INITIALIZED_ROOTS: set[Path] = set()


@dataclass(frozen=True)
class IncidentPaths:
    incident_folder: Path

    @property
    def incident_db(self) -> Path:
        return self.incident_folder / "incident.db"

    @property
    def spatial_db(self) -> Path:
        return self.incident_folder / "spatial.db"

    @property
    def manifest(self) -> Path:
        return self.incident_folder / "incident.json"

    @property
    def forms_generated(self) -> Path:
        return self.incident_folder / "forms" / "generated"

    @property
    def forms_exports(self) -> Path:
        return self.incident_folder / "forms" / "exports"

    @property
    def forms_uploads(self) -> Path:
        return self.incident_folder / "forms" / "uploads"

    @property
    def forms_drafts(self) -> Path:
        return self.incident_folder / "forms" / "drafts"

    @property
    def files_attachments(self) -> Path:
        return self.incident_folder / "files" / "attachments"

    @property
    def files_media(self) -> Path:
        return self.incident_folder / "files" / "media"

    @property
    def files_imports(self) -> Path:
        return self.incident_folder / "files" / "imports"

    @property
    def files_reference_docs(self) -> Path:
        return self.incident_folder / "files" / "reference_docs"

    @property
    def reports(self) -> Path:
        return self.incident_folder / "reports"

    @property
    def exports(self) -> Path:
        return self.incident_folder / "exports"

    @property
    def logs(self) -> Path:
        return self.incident_folder / "logs"

    @property
    def temp(self) -> Path:
        return self.incident_folder / "temp"


def data_root() -> Path:
    root = Path(os.environ.get("CHECKIN_DATA_DIR", "data")).expanduser()
    return root


def master_db_path() -> Path:
    return data_root() / "master.db"


def app_ini_path() -> Path:
    return data_root() / "app.ini"


def incidents_root() -> Path:
    root = data_root() / "incidents"
    root.mkdir(parents=True, exist_ok=True)
    return root


def sanitize_incident_name(raw: object | None, *, fallback: str = "incident") -> str:
    value = str(raw or "").strip()
    if not value:
        return fallback
    value = re.sub(r'[<>:"/|?*]+', '-', value)
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^A-Za-z0-9._-]", "-", value)
    value = value.strip(" .")
    return value or fallback


def build_incident_folder_name(
    *,
    incident_number: object | None,
    incident_name: object | None,
    incident_id: object | None,
) -> str:
    safe_name = sanitize_incident_name(incident_name, fallback="incident")
    if incident_number is not None and str(incident_number).strip():
        base = sanitize_incident_name(incident_number, fallback="incident")
    elif incident_id is not None and str(incident_id).strip():
        base = sanitize_incident_name(incident_id, fallback="incident")
    else:
        base = "incident"
    return f"{base}_{safe_name}"


def incident_paths_from_folder(folder: Path) -> IncidentPaths:
    return IncidentPaths(incident_folder=folder)


def get_incident_paths(
    *, incident_number: object | None, incident_name: object | None, incident_id: object | None
) -> IncidentPaths:
    folder_name = build_incident_folder_name(
        incident_number=incident_number,
        incident_name=incident_name,
        incident_id=incident_id,
    )
    folder = incidents_root() / folder_name
    return IncidentPaths(incident_folder=folder)


def _required_incident_dirs(paths: IncidentPaths) -> list[Path]:
    return [
        paths.forms_generated,
        paths.forms_exports,
        paths.forms_uploads,
        paths.forms_drafts,
        paths.files_attachments,
        paths.files_media,
        paths.files_imports,
        paths.files_reference_docs,
        paths.reports,
        paths.exports,
        paths.logs,
        paths.temp,
    ]


def read_incident_manifest(manifest_path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def write_incident_manifest(paths: IncidentPaths, metadata: dict[str, Any]) -> None:
    payload = {
        "incident_id": metadata.get("incident_id"),
        "incident_number": metadata.get("incident_number"),
        "name": metadata.get("name") or "",
        "status": metadata.get("status") or "Active",
        "type": metadata.get("type") or "",
        "created_at": metadata.get("created_at"),
        "updated_at": metadata.get("updated_at"),
        "incident_db_path": "incident.db",
        "spatial_db_path": "spatial.db",
        "folder_version": FOLDER_VERSION,
    }
    paths.manifest.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def ensure_incident_structure(paths: IncidentPaths, metadata: dict[str, Any] | None = None) -> None:
    paths.incident_folder.mkdir(parents=True, exist_ok=True)
    for directory in _required_incident_dirs(paths):
        directory.mkdir(parents=True, exist_ok=True)
    paths.spatial_db.touch(exist_ok=True)
    if metadata is not None and (not paths.manifest.exists() or metadata.get("updated_at")):
        write_incident_manifest(paths, metadata)


def _master_incident_row_by_number(number: str) -> dict[str, Any] | None:
    db = master_db_path()
    if not db.exists():
        return None
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(
                """
                SELECT id, number, name, status, type, start_time, end_time
                FROM incidents
                WHERE number = ?
                LIMIT 1
                """,
                (number,),
            )
            row = cur.fetchone()
        except sqlite3.OperationalError:
            return None
    return dict(row) if row else None


def infer_incident_metadata(incident_number: str) -> dict[str, Any]:
    row = _master_incident_row_by_number(incident_number)
    if row:
        return {
            "incident_id": row.get("id"),
            "incident_number": row.get("number") or incident_number,
            "name": row.get("name") or incident_number,
            "status": row.get("status") or "Active",
            "type": row.get("type") or "",
            "created_at": row.get("start_time"),
            "updated_at": row.get("end_time") or row.get("start_time"),
        }
    return {
        "incident_id": None,
        "incident_number": incident_number,
        "name": incident_number,
        "status": "Active",
        "type": "",
        "created_at": None,
        "updated_at": None,
    }


def resolve_incident_paths_by_identifier(identifier: object | None) -> IncidentPaths | None:
    if identifier is None or not str(identifier).strip():
        return None
    wanted = str(identifier).strip()
    for folder in incidents_root().iterdir():
        if not folder.is_dir():
            continue
        manifest = read_incident_manifest(folder / "incident.json") or {}
        if str(manifest.get("incident_number") or "") == wanted or str(manifest.get("incident_id") or "") == wanted:
            return IncidentPaths(folder)
    # Compatibility: if old callers pass exact folder name
    folder_candidate = incidents_root() / sanitize_incident_name(wanted, fallback=wanted)
    if folder_candidate.is_dir():
        return IncidentPaths(folder_candidate)
    return None


def list_incident_folders() -> list[IncidentPaths]:
    out: list[IncidentPaths] = []
    for folder in sorted(incidents_root().iterdir()):
        if folder.is_dir():
            out.append(IncidentPaths(folder))
    return out


def migrate_legacy_incident_databases() -> list[tuple[Path, Path]]:
    migrated: list[tuple[Path, Path]] = []
    root = incidents_root()
    logger.debug("incident-storage migration scan root=%s", root)
    for candidate in root.glob("*.db"):
        if candidate.name.lower() in _RESERVED_FILES:
            continue
        incident_number = candidate.stem
        metadata = infer_incident_metadata(incident_number)
        target = get_incident_paths(
            incident_number=metadata.get("incident_number") or incident_number,
            incident_name=metadata.get("name") or incident_number,
            incident_id=metadata.get("incident_id"),
        )
        final_folder = target.incident_folder
        suffix = 1
        while final_folder.exists() and (final_folder / "incident.db").exists():
            existing_manifest = read_incident_manifest(final_folder / "incident.json") or {}
            if str(existing_manifest.get("incident_number") or "") == str(metadata.get("incident_number") or incident_number):
                logger.debug("incident-storage skip already migrated db=%s folder=%s", candidate, final_folder)
                break
            final_folder = Path(f"{target.incident_folder}_{suffix:02d}")
            suffix += 1
        else:
            pass

        if final_folder.exists() and (final_folder / "incident.db").exists():
            continue

        paths = IncidentPaths(final_folder)
        try:
            ensure_incident_structure(paths, metadata)
            shutil.move(str(candidate), str(paths.incident_db))
            write_incident_manifest(paths, metadata)
            logger.info("incident-storage migrated %s -> %s", candidate, paths.incident_db)
            migrated.append((candidate, paths.incident_db))
        except Exception:
            logger.exception("incident-storage migration failed for %s", candidate)
    return migrated


def ensure_layout_initialized() -> None:
    root = data_root()
    root_key = root.resolve()
    if root_key in _INITIALIZED_ROOTS:
        return
    root.mkdir(parents=True, exist_ok=True)
    incidents_root()
    logger.debug("incident-storage initialized root=%s", root)
    migrate_legacy_incident_databases()
    _INITIALIZED_ROOTS.add(root_key)
