"""Public service API used to manage form templates and instances."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from ..models import Field
from . import binder as binder_module
from . import db
from .exporter import PDFExporter


@dataclass(slots=True)
class FormService:
    """High level API consumed by the UI and other modules."""

    binder: binder_module.Binder = binder_module.GLOBAL_BINDER
    exporter: PDFExporter = field(default_factory=PDFExporter)

    # ------------------------------------------------------------------
    # Template operations
    # ------------------------------------------------------------------
    def list_templates(self, category: str | None = None) -> list[dict[str, Any]]:
        """Return templates filtered by ``category`` (if provided)."""

        with db.master_connection() as connection:
            if category:
                rows = connection.execute(
                    "SELECT * FROM form_templates WHERE category = ? ORDER BY name",
                    (category,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM form_templates ORDER BY name",
                ).fetchall()
        return db.rows_to_dicts(rows)

    def get_template(self, template_id: int) -> dict[str, Any]:
        """Return template metadata for ``template_id``."""

        record = self._load_template_record(template_id)
        return record

    def save_template(
        self,
        *,
        name: str,
        category: str | None,
        subcategory: str | None,
        background_path: str,
        page_count: int,
        fields: list[Field | dict[str, Any]],
        version: int | None = None,
        template_id: int | None = None,
    ) -> int:
        """Insert or update a template record and return its ``id``.

        ``fields`` accepts either :class:`Field` instances or already
        serialised dictionaries matching the JSON schema.
        """

        payload = [field.to_dict() if isinstance(field, Field) else field for field in fields]
        fields_json = json.dumps(payload, ensure_ascii=False, indent=None)
        now = datetime.now(timezone.utc).isoformat()

        with db.master_connection() as connection:
            if template_id is None:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO form_templates (
                        name, category, subcategory, background_path,
                        page_count, fields_json, created_at, updated_at, version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        category,
                        subcategory,
                        background_path,
                        page_count,
                        fields_json,
                        now,
                        now,
                        version or 1,
                    ),
                )
                template_id = cursor.lastrowid
            else:
                row = connection.execute(
                    "SELECT version FROM form_templates WHERE id = ?",
                    (template_id,),
                ).fetchone()
                if not row:
                    raise ValueError(f"Template {template_id} does not exist")
                current_version = int(row["version"])
                new_version = version or current_version + 1
                connection.execute(
                    """
                    UPDATE form_templates
                    SET name = ?, category = ?, subcategory = ?, background_path = ?,
                        page_count = ?, fields_json = ?, updated_at = ?, version = ?
                    WHERE id = ?
                    """,
                    (
                        name,
                        category,
                        subcategory,
                        background_path,
                        page_count,
                        fields_json,
                        now,
                        new_version,
                        template_id,
                    ),
                )
                version = new_version

        self._update_template_meta(
            background_path=background_path,
            template_id=template_id,
            template_name=name,
            category=category,
            subcategory=subcategory,
            page_count=page_count,
            version=version or 1,
            fields=payload,
            updated_at=now,
        )

        return int(template_id)

    # ------------------------------------------------------------------
    # Instance operations
    # ------------------------------------------------------------------
    def create_instance(self, incident_id: str, template_id: int, prefill_ctx: dict[str, Any]) -> int:
        """Create a form instance for ``incident_id`` using ``template_id``."""

        template = self._load_template_record(template_id)
        fields = template["fields"]
        template_version = int(template["version"])
        now = datetime.now(timezone.utc).isoformat()

        with db.incident_connection(incident_id) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO form_instances (
                    incident_id, template_id, template_version, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, 'draft', ?, ?)
                """,
                (incident_id, template_id, template_version, now, now),
            )
            instance_id = cursor.lastrowid

            for field in fields:
                field_id = int(field.get("id", 0) or 0)
                value = self._resolve_prefill(field, prefill_ctx)
                cursor.execute(
                    """
                    INSERT INTO instance_values (
                        instance_id, field_id, value, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        instance_id,
                        field_id,
                        db.serialize(value),
                        now,
                        now,
                    ),
                )

        return int(instance_id)

    def save_instance_value(
        self,
        instance_id: int,
        field_id: int,
        value: str | dict[str, Any],
        *,
        incident_id: str,
    ) -> None:
        """Persist a value for a field within an instance."""

        now = datetime.now(timezone.utc).isoformat()
        with db.incident_connection(incident_id) as connection:
            cursor = connection.cursor()
            row = cursor.execute(
                "SELECT id FROM instance_values WHERE instance_id = ? AND field_id = ?",
                (instance_id, field_id),
            ).fetchone()
            if row:
                cursor.execute(
                    """
                    UPDATE instance_values
                    SET value = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (db.serialize(value), now, row["id"]),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO instance_values (
                        instance_id, field_id, value, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        instance_id,
                        field_id,
                        db.serialize(value),
                        now,
                        now,
                    ),
                )

    def finalize_instance(self, incident_id: str, instance_id: int) -> None:
        """Mark an instance as finalised."""

        now = datetime.now(timezone.utc).isoformat()
        with db.incident_connection(incident_id) as connection:
            connection.execute(
                "UPDATE form_instances SET status = 'finalized', updated_at = ? WHERE id = ?",
                (now, instance_id),
            )

    def export_instance_pdf(self, incident_id: str, instance_id: int, out_path: str) -> Path:
        """Export ``instance_id`` to PDF and return the resulting path."""

        with db.incident_connection(incident_id) as connection:
            instance_row = connection.execute(
                "SELECT * FROM form_instances WHERE id = ?",
                (instance_id,),
            ).fetchone()
            if not instance_row:
                raise ValueError(f"Instance {instance_id} not found for incident {incident_id}")
            value_rows = connection.execute(
                "SELECT field_id, value FROM instance_values WHERE instance_id = ?",
                (instance_id,),
            ).fetchall()
        template = self._load_template_record(
            int(instance_row["template_id"]),
            version=int(instance_row["template_version"]),
        )
        values = {
            int(row["field_id"]): db.deserialize(row["value"])
            for row in value_rows
        }
        background_paths = self._resolve_backgrounds(template)
        output_path = Path(out_path)
        return self.exporter.export(
            background_paths=background_paths,
            fields=template["fields"],
            values=values,
            output_path=output_path,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _resolve_prefill(self, field: dict[str, Any], context: dict[str, Any]) -> Any:
        config = field.get("config") or {}
        bindings = config.get("bindings") or []
        for binding in bindings:
            source_type = binding.get("source_type")
            source_ref = binding.get("source_ref")
            if source_type == "static":
                return source_ref
            if source_type == "system" and source_ref:
                resolved = self.binder.resolve(context, source_ref)
                if resolved is not None:
                    return resolved
        default = field.get("default_value")
        return default

    def _load_template_record(self, template_id: int, version: int | None = None) -> dict[str, Any]:
        with db.master_connection() as connection:
            row = connection.execute(
                "SELECT * FROM form_templates WHERE id = ?",
                (template_id,),
            ).fetchone()
        if not row:
            raise ValueError(f"Template {template_id} not found")

        record = dict(row)
        fields_json = record.get("fields_json")
        if isinstance(fields_json, str):
            record["fields"] = json.loads(fields_json)
        else:
            record["fields"] = fields_json or []

        if version and version != record.get("version"):
            meta = self._load_template_meta(record.get("background_path"))
            versions = meta.get("versions", {}) if meta else {}
            snapshot = versions.get(str(version)) or versions.get(int(version))
            if snapshot:
                record["fields"] = snapshot.get("fields", record["fields"])
                record["version"] = version
        return record

    def _resolve_backgrounds(self, template: dict[str, Any]) -> list[Path]:
        base_path = template.get("background_path")
        if not base_path:
            raise ValueError("Template background path missing")
        folder = self._template_folder(base_path)
        page_count = int(template.get("page_count", 1))
        return [folder / f"background_page_{index:03d}.png" for index in range(1, page_count + 1)]

    def _template_folder(self, background_path: str | Path) -> Path:
        path = Path(background_path)
        if not path.is_absolute():
            path = db.DATA_DIR / path
        return path

    def _meta_path(self, background_path: str | Path) -> Path:
        return self._template_folder(background_path) / "meta.json"

    def _load_template_meta(self, background_path: str | Path | None) -> dict[str, Any]:
        if not background_path:
            return {}
        meta_path = self._meta_path(background_path)
        if not meta_path.exists():
            return {}
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _update_template_meta(
        self,
        *,
        background_path: str,
        template_id: int,
        template_name: str,
        category: str | None,
        subcategory: str | None,
        page_count: int,
        version: int,
        fields: list[dict[str, Any]],
        updated_at: str,
    ) -> None:
        meta_path = self._meta_path(background_path)
        meta = self._load_template_meta(background_path)
        versions = meta.setdefault("versions", {})
        versions[str(version)] = {
            "fields": fields,
            "updated_at": updated_at,
        }
        meta.update(
            {
                "template_id": template_id,
                "name": template_name,
                "category": category,
                "subcategory": subcategory,
                "page_count": page_count,
                "background_path": background_path,
                "latest_version": version,
            }
        )
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


__all__ = ["FormService"]

