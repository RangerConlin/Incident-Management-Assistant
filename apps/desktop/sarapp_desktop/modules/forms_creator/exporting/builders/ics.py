from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from modules.forms_creator.exporting.models import ExportRequest, PreparedExport
from modules.forms_creator.exporting.registry import ExportRegistry
from modules.forms_creator.exporting.service import utcnow_seconds
from utils import incident_context


STANDARD_ICS_FORM_IDS = [
    "ics_201",
    "ics_202",
    "ics_203",
    "ics_204",
    "ics_205",
    "ics_205a",
    "ics_206",
    "ics_207",
    "ics_208",
    "ics_209",
    "ics_210",
    "ics_211",
    "ics_213",
    "ics_213rr",
    "ics_214",
    "ics_215",
    "ics_215a",
    "ics_217",
    "ics_218",
    "ics_220",
    "ics_221",
    "ics_230",
    "ics_233",
    "ics_309",
]


def ics_form_key(form_id: str) -> str:
    return f"ics:{_normalize_form_id(form_id)}"


def ics_form_label(form_id: str) -> str:
    suffix = _normalize_form_id(form_id).removeprefix("ics_")
    return f"ICS {suffix.upper()}"


def _normalize_form_id(form_id: str) -> str:
    text = str(form_id or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text.startswith("ics_"):
        return text
    if text.startswith("ics"):
        return f"ics_{text[3:].lstrip('_')}"
    return f"ics_{text}"


def _active_incident_id(request: ExportRequest) -> str:
    incident_id = request.incident_id or incident_context.get_active_incident_id()
    if not incident_id:
        raise RuntimeError("No active incident")
    return str(incident_id)


def _safe_filename_part(value: object, fallback: str) -> str:
    text = str(value or "").strip() or fallback
    text = re.sub(r'[<>:"/\\|?*]+', "-", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^A-Za-z0-9._-]", "-", text)
    return text.strip(" .") or fallback


def _output_path(form_id: str, request: ExportRequest, generated_at: str) -> Path:
    paths = incident_context.get_active_incident_paths()
    paths.forms_generated.mkdir(parents=True, exist_ok=True)
    form_name = _safe_filename_part(form_id, "ics_form")
    timestamp = _safe_filename_part(generated_at[:19].replace(":", "-").replace(" ", "_"), "generated")
    target_parts = []
    if request.target_type:
        target_parts.append(_safe_filename_part(request.target_type, "target"))
    if request.target_id not in (None, ""):
        target_parts.append(_safe_filename_part(request.target_id, "id"))
    target = f"_{'_'.join(target_parts)}" if target_parts else ""
    return paths.forms_generated / f"{form_name}{target}_{timestamp}.pdf"


class IcsFormBuilder:
    """Prepares incident-scoped standard ICS forms for the form engine."""

    def __init__(self, form_id: str) -> None:
        self.form_id = _normalize_form_id(form_id)

    def build(self, request: ExportRequest) -> PreparedExport:
        incident_id = _active_incident_id(request)
        generated_at = utcnow_seconds()
        output_path = _output_path(self.form_id, request, generated_at)
        extra_data = dict(request.options.get("extra_data") or {})
        export_data: dict[str, Any] = {
            "form_id": self.form_id,
            "form_label": ics_form_label(self.form_id),
            "target_type": request.target_type or "",
            "target_id": request.target_id or "",
        }
        existing_export_data = extra_data.get("export")
        if isinstance(existing_export_data, dict):
            export_data = {**existing_export_data, **export_data}
        extra_data["export"] = export_data
        return PreparedExport(
            form_id=self.form_id,
            output_path=output_path,
            incident_id=incident_id,
            form_set_id=request.form_set_id,
            extra_data=extra_data,
            metadata={
                "generated_at": generated_at,
                "form_label": ics_form_label(self.form_id),
                "target_type": request.target_type,
                "target_id": request.target_id,
            },
        )


class Ics203FormBuilder(IcsFormBuilder):
    """Prepares the Organization Assignment List from incident org context."""

    def __init__(self) -> None:
        super().__init__("ics_203")

    def build(self, request: ExportRequest) -> PreparedExport:
        prepared = super().build(request)
        extra_data = dict(prepared.extra_data)
        export_data = dict(extra_data.get("export") or {})
        export_data.update(
            {
                "builder_level": "ics_203",
                "data_domain": "incident_organization",
            }
        )
        extra_data["export"] = export_data
        metadata = {
            **prepared.metadata,
            "builder_level": "ics_203",
            "data_domain": "incident_organization",
        }
        return PreparedExport(
            form_id=prepared.form_id,
            output_path=prepared.output_path,
            incident_id=prepared.incident_id,
            form_set_id=prepared.form_set_id,
            extra_data=extra_data,
            metadata=metadata,
        )


def register_ics_builders(registry: ExportRegistry) -> None:
    for form_id in STANDARD_ICS_FORM_IDS:
        if _normalize_form_id(form_id) == "ics_203":
            builder = Ics203FormBuilder()
        else:
            builder = IcsFormBuilder(form_id)
        registry.register(ics_form_key(form_id), builder)
        registry.register(form_id, builder)
        registry.register(ics_form_label(form_id), builder)
