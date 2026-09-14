from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from modules.forms_creator.exporting.models import ExportRequest, PreparedExport
from modules.forms_creator.exporting.registry import ExportRegistry
from modules.forms_creator.exporting.service import utcnow_seconds
from utils import incident_context


GENERIC_FORM_IDS = [
    "ics_225",
    "sar_100",
    "sar_100a",
    "sar_100b",
    "sar_102",
    "sar_110",
    "sar_112",
    "sar_115",
    "sar_116",
    "sar_119",
    "sar_125",
    "sar_125a",
    "sar_131",
    "sar_132",
    "sar_134",
    "sar_301",
    "sar_301a",
    "sar_302",
    "sar_304",
    "sar_305",
    "sar_306",
    "sar_307",
    "capf_104",
    "capf_104a",
    "capf_106",
    "capf_160",
    "miwgf_52",
]


def generic_form_key(form_id: str) -> str:
    return f"form:{_normalize_form_id(form_id)}"


def generic_form_label(form_id: str) -> str:
    normalized = _normalize_form_id(form_id)
    prefix, _, suffix = normalized.partition("_")
    if prefix == "ics":
        return f"ICS {suffix.upper()}"
    if prefix == "sar":
        return f"SAR {suffix.upper()}"
    if prefix == "capf":
        return f"CAPF {suffix.upper()}"
    if prefix == "miwgf":
        return f"MIWGF {suffix.upper()}"
    return normalized.upper().replace("_", " ")


def _normalize_form_id(form_id: str) -> str:
    text = str(form_id or "").strip().lower().replace("-", "_").replace(" ", "_")
    compact = text.replace("_", "")
    if compact.startswith("ics") and not text.startswith("ics_"):
        return f"ics_{compact[3:]}"
    if compact.startswith("sar") and not text.startswith("sar_"):
        return f"sar_{compact[3:]}"
    if compact.startswith("capf") and not text.startswith("capf_"):
        return f"capf_{compact[4:]}"
    if compact.startswith("miwgf") and not text.startswith("miwgf_"):
        return f"miwgf_{compact[5:]}"
    return text


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
    form_name = _safe_filename_part(form_id, "form")
    timestamp = _safe_filename_part(generated_at[:19].replace(":", "-").replace(" ", "_"), "generated")
    target_parts = []
    if request.target_type:
        target_parts.append(_safe_filename_part(request.target_type, "target"))
    if request.target_id not in (None, ""):
        target_parts.append(_safe_filename_part(request.target_id, "id"))
    target = f"_{'_'.join(target_parts)}" if target_parts else ""
    return paths.forms_generated / f"{form_name}{target}_{timestamp}.pdf"


class GenericFormBuilder:
    """Fallback builder for forms without form-specific export logic."""

    def __init__(self, form_id: str) -> None:
        self.form_id = _normalize_form_id(form_id)

    def build(self, request: ExportRequest) -> PreparedExport:
        incident_id = _active_incident_id(request)
        generated_at = utcnow_seconds()
        extra_data = dict(request.options.get("extra_data") or {})
        export_data: dict[str, Any] = {
            "form_id": self.form_id,
            "form_label": generic_form_label(self.form_id),
            "target_type": request.target_type or "",
            "target_id": request.target_id or "",
            "builder_level": "generic",
        }
        existing_export_data = extra_data.get("export")
        if isinstance(existing_export_data, dict):
            export_data = {**existing_export_data, **export_data}
        extra_data["export"] = export_data
        return PreparedExport(
            form_id=self.form_id,
            output_path=_output_path(self.form_id, request, generated_at),
            incident_id=incident_id,
            form_set_id=request.form_set_id,
            extra_data=extra_data,
            metadata={
                "generated_at": generated_at,
                "form_label": generic_form_label(self.form_id),
                "target_type": request.target_type,
                "target_id": request.target_id,
                "builder_level": "generic",
            },
        )


def register_generic_builders(registry: ExportRegistry) -> None:
    for form_id in GENERIC_FORM_IDS:
        builder = GenericFormBuilder(form_id)
        registry.register(generic_form_key(form_id), builder)
        registry.register(form_id, builder)
        registry.register(generic_form_label(form_id), builder)
