"""High level service API for the form creator module.

The :class:`FormService` encapsulates the persistence, binding and exporting
behaviour required by both the Qt authoring UI and other application modules.
It intentionally avoids any Qt specific code so the service can be reused from
command line utilities and tests.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ..models import Field
from . import db
from .binder import Binder
from .exporter import PDFExporter

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def _utcnow() -> str:
    """Return a UTC timestamp suitable for storage in SQLite."""

    return datetime.now(timezone.utc).strftime(ISO_FORMAT)


def _serialise_value(value: Any) -> str | None:
    """Serialise a Python value for storage in the ``instance_values`` table."""

    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return "__JSON__" + json.dumps(value, ensure_ascii=False)
    return str(value)


def _deserialise_value(value: str | None) -> Any:
    """Inverse operation of :func:`_serialise_value`."""

    if value is None:
        return None
    if value.startswith("__JSON__"):
        try:
            return json.loads(value[len("__JSON__") :])
        except json.JSONDecodeError:
            return value
    return value


class FormService:
    """Service facade that manages templates and form instances."""

    def __init__(self, *, data_dir: Path | str = Path("data"), binder: Binder | None = None, exporter: PDFExporter | None = None):
        self.data_dir = Path(data_dir)
        self.forms_dir = self.data_dir / "forms"
        self.forms_dir.mkdir(parents=True, exist_ok=True)
        self.templates_dir = self.forms_dir / "templates"
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        custom_bindings_path = self.forms_dir / "custom_bindings.json"
        self.binder = binder or Binder(custom_bindings_path=custom_bindings_path)
        self.exporter = exporter or PDFExporter(base_data_dir=self.data_dir)
        db.init_master_db()
        self.template_table = self._ensure_template_table()

    # ------------------------------------------------------------------
    # Template helpers
    # ------------------------------------------------------------------
    def list_templates(self, category: str | None = None) -> list[dict[str, Any]]:
        """Return template dictionaries from the master database."""

        with db.get_master_connection() as conn:
            query = f"SELECT * FROM {self.template_table}"
            params: tuple[Any, ...] = ()
            if category:
                query += " WHERE category = ?"
                params = (category,)
            query += " ORDER BY name ASC, version DESC"
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
        return [self._row_to_template_dict(row) for row in rows]

    def get_template(self, template_id: int) -> dict[str, Any]:
        """Fetch a specific template as a dictionary."""

        with db.get_master_connection() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.template_table} WHERE id = ?",
                (template_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Template {template_id} not found")
        return self._row_to_template_dict(row)

    def save_template(
        self,
        *,
        name: str,
        category: str | None,
        subcategory: str | None,
        background_path: str,
        page_count: int,
        fields: Iterable[dict[str, Any] | Field],
        version: int | None = None,
        template_id: int | None = None,
        schema_version: int = 1,
    ) -> int:
        """Insert or update a template.

        Parameters mirror the master schema.  ``fields`` should be an iterable
        of dictionaries (or :class:`~modules.forms_creator.models.Field`
        instances) that are JSON serialisable.  The canonical ``meta.json`` in
        the template's asset directory is refreshed on each save so external
        tools (such as the profile manager) can immediately consume updates.
        """

        fields_payload = [self._normalise_field(field) for field in fields]
        serialised_fields = json.dumps(fields_payload, ensure_ascii=False)
        now = _utcnow()

        persisted_row: dict[str, Any] | None = None

        with db.get_master_connection() as conn:
            if template_id is None:
                new_version = version or 1
                cursor = conn.execute(
                    f"""
                    INSERT INTO {self.template_table}
                      (name, category, subcategory, version, background_path, page_count, schema_version, fields_json, created_at, updated_at, is_active)
                    VALUES
                      (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        name,
                        category,
                        subcategory,
                        new_version,
                        background_path,
                        page_count,
                        schema_version,
                        serialised_fields,
                        now,
                        now,
                    ),
                )
                template_id = cursor.lastrowid
            else:
                existing = conn.execute(
                    f"SELECT * FROM {self.template_table} WHERE id = ?",
                    (template_id,),
                ).fetchone()
                if existing is None:
                    raise ValueError(f"Template {template_id} not found")
                self._archive_template_snapshot(existing)
                current_version = existing["version"]
                new_version = version or (current_version + 1)
                conn.execute(
                    f"""
                    UPDATE {self.template_table}
                       SET name = ?,
                           category = ?,
                           subcategory = ?,
                           version = ?,
                           background_path = ?,
                           page_count = ?,
                           schema_version = ?,
                           fields_json = ?,
                           updated_at = ?
                     WHERE id = ?
                    """,
                    (
                        name,
                        category,
                        subcategory,
                        new_version,
                        background_path,
                        page_count,
                        schema_version,
                        serialised_fields,
                        now,
                        template_id,
                    ),
                )

            persisted = conn.execute(
                f"SELECT * FROM {self.template_table} WHERE id = ?",
                (template_id,),
            ).fetchone()
            if persisted is not None:
                persisted_row = dict(persisted)

        if persisted_row is not None:
            self._write_template_files(persisted_row, fields_payload)

        return int(template_id)

    # ------------------------------------------------------------------
    # Instance helpers
    # ------------------------------------------------------------------
    def create_instance(self, incident_id: str, template_id: int, prefill_ctx: dict[str, Any] | None = None) -> int:
        """Create a form instance for the specified incident."""

        template_row = self.get_template(template_id)
        db.ensure_incident_db(incident_id)
        now = _utcnow()
        template_version = template_row["version"]
        fields = template_row["fields"]
        ctx = prefill_ctx or {}

        with db.get_incident_connection(incident_id) as conn:
            cursor = conn.execute(
                """
                INSERT INTO form_instances (incident_id, template_id, template_version, status, created_at, updated_at)
                VALUES (?, ?, ?, 'draft', ?, ?)
                """,
                (incident_id, template_id, template_version, now, now),
            )
            instance_id = cursor.lastrowid
            for field in fields:
                value = self._prefill_value(field, ctx)
                if value is None:
                    continue
                conn.execute(
                    """
                    INSERT INTO instance_values (instance_id, field_id, value, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (instance_id, field["id"], _serialise_value(value), now, now),
                )
        return instance_id

    def save_instance_value(self, instance_id: int, field_id: int, value: Any, *, incident_id: str) -> None:
        """Persist a single field value for a form instance."""

        db.ensure_incident_db(incident_id)
        now = _utcnow()
        serialised = _serialise_value(value)

        with db.get_incident_connection(incident_id) as conn:
            cursor = conn.execute(
                "SELECT id FROM instance_values WHERE instance_id = ? AND field_id = ?",
                (instance_id, field_id),
            )
            row = cursor.fetchone()
            if row:
                conn.execute(
                    "UPDATE instance_values SET value = ?, updated_at = ? WHERE id = ?",
                    (serialised, now, row["id"]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO instance_values (instance_id, field_id, value, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (instance_id, field_id, serialised, now, now),
                )
            conn.execute(
                "UPDATE form_instances SET updated_at = ? WHERE id = ?",
                (now, instance_id),
            )

    def finalize_instance(self, incident_id: str, instance_id: int) -> None:
        """Mark an instance as finalised."""

        db.ensure_incident_db(incident_id)
        now = _utcnow()
        with db.get_incident_connection(incident_id) as conn:
            conn.execute(
                "UPDATE form_instances SET status = 'finalized', updated_at = ? WHERE id = ?",
                (now, instance_id),
            )

    def export_instance_pdf(self, incident_id: str, instance_id: int, out_path: str | Path) -> str:
        """Composite a filled template into a printable PDF."""

        db.ensure_incident_db(incident_id)
        with db.get_incident_connection(incident_id) as conn:
            instance_row = conn.execute("SELECT * FROM form_instances WHERE id = ?", (instance_id,)).fetchone()
            if instance_row is None:
                raise ValueError(f"Instance {instance_id} not found for incident {incident_id}")
            values_cursor = conn.execute(
                "SELECT field_id, value FROM instance_values WHERE instance_id = ?",
                (instance_id,),
            )
            value_map = {row["field_id"]: _deserialise_value(row["value"]) for row in values_cursor.fetchall()}

        template_data = self._load_template_version(instance_row["template_id"], instance_row["template_version"])
        output = self.exporter.export_instance(template_data, value_map, Path(out_path))
        return str(output)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_template_table(self) -> str:
        required = {
            "id",
            "name",
            "category",
            "subcategory",
            "version",
            "background_path",
            "page_count",
            "schema_version",
            "fields_json",
            "created_at",
            "updated_at",
            "is_active",
        }
        fallback_table = "form_templates_hybrid"
        with db.get_master_connection() as conn:
            try:
                info = conn.execute("PRAGMA table_info(form_templates)").fetchall()
            except Exception:
                info = []
            columns = {row["name"] for row in info}
            if not info:
                conn.executescript(db._create_template_sql("form_templates"))
                return "form_templates"
            if required.issubset(columns):
                return "form_templates"
            conn.executescript(db._create_template_sql(fallback_table))
        return fallback_table

    def _row_to_template_dict(self, row: Any) -> dict[str, Any]:
        payload = dict(row)
        payload["fields"] = json.loads(payload.pop("fields_json"))
        return payload

    def _normalise_field(self, field: dict[str, Any] | Field) -> dict[str, Any]:
        if is_dataclass(field):
            field_dict = asdict(field)
        else:
            field_dict = dict(field)
        field_dict.setdefault("config", {})
        field_dict.setdefault("bindings", field_dict.get("config", {}).get("bindings", []))
        # Normalise config keys
        config = field_dict.get("config") or {}
        config.setdefault("bindings", field_dict.pop("bindings", config.get("bindings", [])))
        config.setdefault("validations", config.get("validations", []))
        config.setdefault("dropdown", config.get("dropdown"))
        config.setdefault("table", config.get("table"))
        field_dict["config"] = config
        return field_dict

    def _prefill_value(self, field: dict[str, Any], context: dict[str, Any]) -> Any:
        value = field.get("default_value") or None
        config = field.get("config") or {}
        for binding in config.get("bindings", []):
            source_type = binding.get("source_type")
            if source_type == "static":
                value = binding.get("value")
            elif source_type == "system":
                key = binding.get("source_ref")
                if key:
                    try:
                        value = self.binder.resolve(context, key)
                    except Exception:
                        continue
        return value

    def _archive_template_snapshot(self, row: Any) -> None:
        """Persist the previous template definition to disk for version history."""

        background = Path(row["background_path"])
        if not background.is_absolute():
            background = self.data_dir / background
        versions_dir = background / "versions"
        versions_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = versions_dir / f"template_v{row['version']:03d}.json"
        snapshot = dict(row)
        snapshot["fields"] = json.loads(snapshot.pop("fields_json"))
        with snapshot_path.open("w", encoding="utf-8") as fh:
            json.dump(snapshot, fh, ensure_ascii=False, indent=2)

    def _load_template_version(self, template_id: int, version: int) -> dict[str, Any]:
        with db.get_master_connection() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.template_table} WHERE id = ?",
                (template_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Template {template_id} not found")

        current_version = row["version"]
        if version == current_version:
            return self._row_to_template_dict(row)

        if version > current_version:
            raise ValueError(
                f"Requested template version {version} is newer than stored version {current_version}"
            )

        background = Path(row["background_path"])
        if not background.is_absolute():
            background = self.data_dir / background
        snapshot_path = background / "versions" / f"template_v{version:03d}.json"
        if not snapshot_path.exists():
            raise FileNotFoundError(
                f"Template version {version} for template {template_id} is not available. Expected {snapshot_path}."
            )
        with snapshot_path.open("r", encoding="utf-8") as fh:
            snapshot = json.load(fh)
        snapshot["id"] = template_id
        return snapshot

    def _write_template_files(self, row: dict[str, Any], fields: list[dict[str, Any]]) -> None:
        """Persist the canonical ``meta.json`` alongside the template assets."""

        background = Path(row.get("background_path", ""))
        if not background.is_absolute():
            background = self.data_dir / background
        background.mkdir(parents=True, exist_ok=True)

        template_uuid = background.name
        page_count = int(row.get("page_count", 1) or 1)
        pages = [f"background_page_{index + 1:03d}.png" for index in range(page_count)]

        payload = {
            "id": row.get("id"),
            "template_uuid": template_uuid,
            "name": row.get("name"),
            "category": row.get("category"),
            "subcategory": row.get("subcategory"),
            "version": row.get("version"),
            "schema_version": row.get("schema_version"),
            "background_path": row.get("background_path"),
            "page_count": page_count,
            "background_pages": pages,
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "fields": fields,
        }

        meta_path = background / "meta.json"
        with meta_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
