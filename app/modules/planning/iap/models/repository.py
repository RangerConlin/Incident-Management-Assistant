"""Persistence layer for the IAP Builder.

This module provides a minimal yet functional repository that persists
Incident Action Plan (IAP) packages and their forms in the active incident's
SQLite database.  The implementation intentionally focuses on the operations
required by the initial UI scaffolding – storing and retrieving packages and
forms.  Audit history and validation hooks will be layered in during later
milestones.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Iterable, List, Optional

from .iap_models import FormInstance, IAPPackage

__all__ = ["IAPRepository"]


class IAPRepository:
    """Encapsulates read/write operations for IAP packages and forms."""

    def __init__(self, incident_db: Path, master_db: Path | None = None):
        self.incident_db = Path(incident_db)
        self.incident_db.parent.mkdir(parents=True, exist_ok=True)
        self.master_db = Path(master_db) if master_db else None
        self._initialized = False

    # -- lifecycle -----------------------------------------------------------------
    def initialize(self) -> None:
        """Ensure the required SQLite tables exist."""

        with self._connect() as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS iap_packages (
                    incident_id TEXT NOT NULL,
                    op_number INTEGER NOT NULL,
                    op_start TEXT NOT NULL,
                    op_end TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    notes TEXT DEFAULT '',
                    version_tag TEXT,
                    published_pdf_path TEXT,
                    PRIMARY KEY (incident_id, op_number)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS iap_forms (
                    incident_id TEXT NOT NULL,
                    op_number INTEGER NOT NULL,
                    form_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'draft',
                    last_updated TEXT NOT NULL,
                    fields_json TEXT,
                    attachments_json TEXT,
                    PRIMARY KEY (incident_id, op_number, form_id),
                    FOREIGN KEY (incident_id, op_number)
                        REFERENCES iap_packages(incident_id, op_number)
                        ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS iap_changelog (
                    incident_id TEXT NOT NULL,
                    op_number INTEGER NOT NULL,
                    form_id TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    user_id TEXT,
                    field TEXT,
                    old_value TEXT,
                    new_value TEXT
                )
                """
            )
            conn.commit()
        self._initialized = True

    # -- package operations ---------------------------------------------------------
    def list_packages(self, incident_id: str) -> List[IAPPackage]:
        """Return all packages for ``incident_id`` ordered by operational period."""

        self._ensure_initialized()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT incident_id, op_number, op_start, op_end, created_at,
                       status, notes, version_tag, published_pdf_path
                FROM iap_packages
                WHERE incident_id = ?
                ORDER BY op_number
                """,
                (incident_id,),
            ).fetchall()
            packages = [self._row_to_package(row) for row in rows]
            for package in packages:
                package.forms = self._load_forms(conn, package.incident_id, package.op_number)
            return packages

    def get_package(self, incident_id: str, op_number: int) -> IAPPackage:
        """Fetch a single package for ``incident_id`` and ``op_number``."""

        self._ensure_initialized()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT incident_id, op_number, op_start, op_end, created_at,
                       status, notes, version_tag, published_pdf_path
                FROM iap_packages
                WHERE incident_id = ? AND op_number = ?
                """,
                (incident_id, op_number),
            ).fetchone()
            if row is None:
                raise KeyError(f"No IAP package for incident {incident_id!r} OP {op_number}")
            package = self._row_to_package(row)
            package.forms = self._load_forms(conn, incident_id, op_number)
            return package

    def save_package(self, package: IAPPackage) -> IAPPackage:
        """Insert or update ``package`` in the database."""

        self._ensure_initialized()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO iap_packages (
                    incident_id, op_number, op_start, op_end, created_at,
                    status, notes, version_tag, published_pdf_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(incident_id, op_number) DO UPDATE SET
                    op_start = excluded.op_start,
                    op_end = excluded.op_end,
                    status = excluded.status,
                    notes = excluded.notes,
                    version_tag = excluded.version_tag,
                    published_pdf_path = excluded.published_pdf_path
                """,
                (
                    package.incident_id,
                    package.op_number,
                    self._serialize_dt(package.op_start),
                    self._serialize_dt(package.op_end),
                    self._serialize_dt(package.created_at),
                    package.status,
                    package.notes,
                    package.version_tag,
                    package.published_pdf_path,
                ),
            )
            conn.commit()
        return package

    # -- form operations ------------------------------------------------------------
    def save_form(self, package: IAPPackage, form: FormInstance) -> FormInstance:
        """Persist ``form`` as part of ``package``."""

        self._ensure_initialized()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO iap_forms (
                    incident_id, op_number, form_id, title, revision, status,
                    last_updated, fields_json, attachments_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(incident_id, op_number, form_id) DO UPDATE SET
                    title = excluded.title,
                    revision = excluded.revision,
                    status = excluded.status,
                    last_updated = excluded.last_updated,
                    fields_json = excluded.fields_json,
                    attachments_json = excluded.attachments_json
                """,
                (
                    package.incident_id,
                    package.op_number,
                    form.form_id,
                    form.title,
                    form.revision,
                    form.status,
                    self._serialize_dt(form.last_updated),
                    json.dumps(form.fields or {}),
                    json.dumps(form.attachments or []),
                ),
            )
            conn.commit()
        return form

    def save_forms(self, package: IAPPackage, forms: Iterable[FormInstance]) -> None:
        """Bulk persist forms."""

        for form in forms:
            self.save_form(package, form)

    def changelog_for_form(self, form_id: int) -> List[dict]:
        """Return change log entries for the database row ``form_id``."""

        # Change log support will be implemented in a later milestone.
        return []

    # -- metadata helpers -----------------------------------------------------------
    def incident_name(self, incident_id: str) -> Optional[str]:
        """Look up the human friendly incident name from the master database."""

        if not self.master_db or not self.master_db.exists():
            return None
        try:
            with sqlite3.connect(os.fspath(self.master_db)) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT name FROM incidents WHERE number = ? LIMIT 1",
                    (incident_id,),
                ).fetchone()
                if row and row["name"]:
                    return str(row["name"])
        except sqlite3.Error:
            return None
        return None

    # -- internal utilities --------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(os.fspath(self.incident_db))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=3000")
        return conn

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            self.initialize()

    def _load_forms(self, conn: sqlite3.Connection, incident_id: str, op_number: int) -> List[FormInstance]:
        rows = conn.execute(
            """
            SELECT form_id, title, revision, status, last_updated,
                   fields_json, attachments_json
            FROM iap_forms
            WHERE incident_id = ? AND op_number = ?
            ORDER BY form_id
            """,
            (incident_id, op_number),
        ).fetchall()
        forms: List[FormInstance] = []
        for row in rows:
            fields = self._decode_json(row["fields_json"], {})
            attachments = self._decode_json(row["attachments_json"], [])
            last_updated = self._parse_dt(row["last_updated"])
            forms.append(
                FormInstance(
                    form_id=row["form_id"],
                    title=row["title"],
                    op_number=op_number,
                    revision=int(row["revision"]),
                    fields=fields,
                    attachments=attachments,
                    status=row["status"],
                    last_updated=last_updated,
                )
            )
        return forms

    def _row_to_package(self, row: sqlite3.Row) -> IAPPackage:
        return IAPPackage(
            incident_id=row["incident_id"],
            op_number=int(row["op_number"]),
            op_start=self._parse_dt(row["op_start"]),
            op_end=self._parse_dt(row["op_end"]),
            created_at=self._parse_dt(row["created_at"]),
            status=row["status"],
            notes=row["notes"] or "",
            version_tag=row["version_tag"],
            published_pdf_path=row["published_pdf_path"],
        )

    @staticmethod
    def _parse_dt(value: str | None) -> datetime:
        if value:
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                pass
        return datetime.utcnow()

    @staticmethod
    def _serialize_dt(value: datetime) -> str:
        return value.replace(microsecond=0).isoformat()

    @staticmethod
    def _decode_json(payload: str | None, default: object) -> object:
        if not payload:
            return default
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return default
