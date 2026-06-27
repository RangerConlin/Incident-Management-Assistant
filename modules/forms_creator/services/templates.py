"""High level service API for the form creator module.

The :class:`FormService` encapsulates the persistence, binding and exporting
behaviour required by both the Qt authoring UI and other application modules.
It intentionally avoids any Qt specific code so the service can be reused from
command line utilities and tests.

Persistence goes through the master/incident HTTP API (`utils.api_client`),
backed by MongoDB (`data/db/sarapp_db/api/routers/forms.py`). That API models
forms as family -> template -> version: family is the issuing agency (FEMA,
CAP, SAR, ICS Canada, USCG, Custom), template is one form within that
agency's set (e.g. FEMA's ICS 204), and version is a specific revision of
that form's layout/fields over time. This module flattens that shape back
into the single dict per template that the rest of forms_creator expects.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ..models import Field
from .binder import Binder
from .exporter import PDFExporter

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def _client():
    from utils.api_client import api_client

    return api_client


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime(ISO_FORMAT)


def _serialise_value(value: Any) -> str | None:
    """Serialise a Python value for storage in a form instance's values map."""

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

    # ------------------------------------------------------------------
    # Family (agency) helpers
    # ------------------------------------------------------------------
    def _get_or_create_family(self, agency_code: str) -> dict[str, Any]:
        code = agency_code.strip().upper() if agency_code else "CUSTOM"
        families = _client().get("/api/forms/families", params={"code": code}) or []
        if families:
            return families[0]
        return _client().post(
            "/api/forms/families",
            json={"code": code, "title": code, "category": None, "default_agency": None, "is_active": True},
        )

    # ------------------------------------------------------------------
    # Template helpers
    # ------------------------------------------------------------------
    def list_templates(self, category: str | None = None) -> list[dict[str, Any]]:
        """Return template dictionaries, optionally filtered by agency (``category``)."""

        # The list endpoint doesn't embed each template's current version, so
        # callers only get id/name/category/subcategory metadata here, not
        # fields/background_path. Use get_template() for the full picture.
        params = {"agency": category.strip().upper()} if category else {}
        templates = _client().get("/api/forms/templates", params=params) or []
        return [self._flatten_template(t) for t in templates]

    def get_template(self, template_id: int) -> dict[str, Any]:
        """Fetch a specific template as a flattened dictionary."""

        doc = _client().get(f"/api/forms/templates/{template_id}")
        if doc is None:
            raise ValueError(f"Template {template_id} not found")
        return self._flatten_template(doc)

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

        ``category`` is the issuing agency (e.g. ``"FEMA"``, ``"CAP"``) and
        maps onto the family. ``subcategory`` is the form code within that
        agency (e.g. ``"ICS_204"``); it defaults to a slug of ``name`` when
        omitted. Saving against an existing ``template_id`` creates a new
        version under that template rather than mutating one in place.
        """

        fields_payload = [self._normalise_field(field) for field in fields]
        layout = {
            "background_path": background_path,
            "page_count": page_count,
            "schema_version": schema_version,
        }

        if template_id is None:
            family = self._get_or_create_family(category or "CUSTOM")
            code = (subcategory or name).strip().upper().replace(" ", "_")
            template = _client().post(
                "/api/forms/templates",
                json={
                    "family_id": family["id"],
                    "agency": family["code"],
                    "code": code,
                    "title": name,
                    "status": "active",
                },
            )
            template_id = template["id"]
            version_number = version or 1
        else:
            existing = _client().get(f"/api/forms/templates/{template_id}")
            if existing is None:
                raise ValueError(f"Template {template_id} not found")
            current_version_number = (existing.get("current_version") or {}).get("version_number", 0)
            version_number = version or (current_version_number + 1)

        version_doc = _client().post(
            f"/api/forms/templates/{template_id}/versions",
            json={
                "version_number": version_number,
                "layout": layout,
                "fields": fields_payload,
            },
        )

        persisted_row = self._flatten_template(
            _client().get(f"/api/forms/templates/{template_id}"),
            version_override=version_doc,
        )
        self._write_template_files(persisted_row, fields_payload)

        return int(template_id)

    # ------------------------------------------------------------------
    # Instance helpers
    # ------------------------------------------------------------------
    def create_instance(self, incident_id: str, template_id: int, prefill_ctx: dict[str, Any] | None = None) -> int:
        """Create a form instance for the specified incident."""

        template_row = self.get_template(template_id)
        ctx = prefill_ctx or {}

        created = _client().post(
            f"/api/incidents/{incident_id}/forms",
            json={
                "family_id": template_row["family_id"],
                "template_id": template_id,
                "template_version_id": template_row["version_id"],
                "title": template_row["name"],
                "agency": template_row["category"],
                "status": "draft",
            },
        )
        instance_id = created["id"]

        updates: dict[str, Any] = {}
        for field in template_row["fields"]:
            value = self._prefill_value(field, ctx)
            if value is None:
                continue
            updates[str(field["id"])] = {"value": _serialise_value(value), "source_type": "system"}
        if updates:
            _client().patch(
                f"/api/incidents/{incident_id}/forms/{instance_id}/values",
                json={"updates": updates, "require_override_reason": False},
            )
        return instance_id

    def save_instance_value(self, instance_id: int, field_id: int, value: Any, *, incident_id: str) -> None:
        """Persist a single field value for a form instance."""

        serialised = _serialise_value(value)
        _client().patch(
            f"/api/incidents/{incident_id}/forms/{instance_id}/values",
            json={"updates": {str(field_id): {"value": serialised, "source_type": "manual"}}, "require_override_reason": False},
        )

    def finalize_instance(self, incident_id: str, instance_id: int) -> None:
        """Mark an instance as finalised."""

        _client().post(f"/api/incidents/{incident_id}/forms/{instance_id}/finalize", json={})

    def export_instance_pdf(self, incident_id: str, instance_id: int, out_path: str | Path) -> str:
        """Composite a filled template into a printable PDF."""

        instance_row = _client().get(f"/api/incidents/{incident_id}/forms/{instance_id}")
        if instance_row is None:
            raise ValueError(f"Instance {instance_id} not found for incident {incident_id}")

        value_map: dict[int, Any] = {}
        for field_key, vdoc in (instance_row.get("values") or {}).items():
            try:
                key = int(field_key)
            except (TypeError, ValueError):
                continue
            value_map[key] = _deserialise_value(vdoc.get("value"))

        template_data = self._load_template_version(
            instance_row["template_id"], instance_row["template_version_id"]
        )
        output = self.exporter.export_instance(template_data, value_map, Path(out_path))
        return str(output)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _flatten_template(self, doc: dict[str, Any], *, version_override: dict[str, Any] | None = None) -> dict[str, Any]:
        version = version_override or doc.get("current_version") or {}
        layout = version.get("layout") or {}
        return {
            "id": doc["id"],
            "family_id": doc.get("family_id"),
            "version_id": version.get("id"),
            "name": doc.get("title", ""),
            "category": doc.get("agency", ""),
            "subcategory": doc.get("code", ""),
            "version": version.get("version_number", 1),
            "background_path": layout.get("background_path", ""),
            "page_count": layout.get("page_count", 1),
            "schema_version": layout.get("schema_version", 1),
            "fields": version.get("fields", []),
            "created_at": doc.get("created_at", ""),
            "updated_at": doc.get("updated_at", ""),
            "is_active": 1 if doc.get("status", "active") == "active" else 0,
        }

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

    def _load_template_version(self, template_id: int, version_id: int) -> dict[str, Any]:
        version = _client().get(f"/api/forms/templates/{template_id}/versions/{version_id}")
        if version is None:
            raise ValueError(f"Template version {version_id} not found for template {template_id}")
        template = _client().get(f"/api/forms/templates/{template_id}")
        if template is None:
            raise ValueError(f"Template {template_id} not found")
        return self._flatten_template(template, version_override=version)

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
