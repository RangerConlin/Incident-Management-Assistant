from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from modules.forms_creator.exporting.models import ExportRequest, PreparedExport
from modules.forms_creator.exporting.registry import ExportRegistry
from modules.forms_creator.exporting.service import utcnow_seconds
from modules.forms_creator.context import FormDataContext
from modules.operations.taskings import repository as taskings_repository
from utils import incident_context


# form_id -> default form_set_id
TASK_ASSIGNMENT_FORM_IDS: dict[str, str] = {
    "sar_104": "sar",
    "capf_109": "cap",
}


def task_assignment_form_key(form_id: str) -> str:
    return f"task_assignment:{_normalize_form_id(form_id)}"


def task_assignment_form_label(form_id: str) -> str:
    normalized = _normalize_form_id(form_id)
    prefix, _, suffix = normalized.partition("_")
    if prefix == "sar":
        return f"SAR {suffix.upper()}"
    if prefix == "capf":
        return f"CAPF {suffix.upper()}"
    return normalized.upper().replace("_", " ")


def _normalize_form_id(form_id: str) -> str:
    text = str(form_id or "").strip().lower().replace("-", "_").replace(" ", "_")
    compact = text.replace("_", "")
    if compact.startswith("sar") and not text.startswith("sar_"):
        return f"sar_{compact[3:]}"
    if compact.startswith("capf") and not text.startswith("capf_"):
        return f"capf_{compact[4:]}"
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


def _output_path(form_id: str, context: dict[str, Any], generated_at: str) -> Path:
    paths = incident_context.get_active_incident_paths()
    paths.forms_generated.mkdir(parents=True, exist_ok=True)
    task_id = _safe_filename_part((context.get("task") or {}).get("task_id"), "task")
    form_name = _safe_filename_part(form_id, "form")
    timestamp = _safe_filename_part(generated_at[:19].replace(":", "-").replace(" ", "_"), "generated")
    return paths.forms_generated / f"{task_id}_{form_name}_{timestamp}.pdf"


class TaskAssignmentFormBuilder:
    """Prepares task/team-scoped assignment form exports (e.g. SAR 104) from live
    task, team, and assignment data via
    ``taskings_repository._build_assignment_export_context``.
    """

    def __init__(self, form_id: str) -> None:
        self.form_id = _normalize_form_id(form_id)
        self.form_set_id = TASK_ASSIGNMENT_FORM_IDS[self.form_id]

    def build(self, request: ExportRequest) -> PreparedExport:
        if request.target_id in (None, ""):
            raise ValueError(f"{self.form_id} export requires target_id (a task id)")
        incident_id = _active_incident_id(request)
        task_id = int(request.target_id)
        team = request.options.get("team")

        context = taskings_repository._build_assignment_export_context(task_id, team)

        generated_at = utcnow_seconds()
        output_path = _output_path(self.form_id, context, generated_at)

        extra_data = dict(context)
        debrief_id = request.options.get("debrief_id")
        if debrief_id not in (None, ""):
            extra_data["debrief"] = FormDataContext().build_debrief(int(debrief_id), incident_id)
        manual = request.options.get("extra_data")
        if isinstance(manual, dict):
            extra_data = {**extra_data, **manual}

        return PreparedExport(
            form_id=self.form_id,
            output_path=output_path,
            incident_id=incident_id,
            form_set_id=request.form_set_id or self.form_set_id,
            extra_data=extra_data,
            metadata={
                "generated_at": generated_at,
                "form_label": task_assignment_form_label(self.form_id),
                "builder_level": self.form_id,
                "target_type": request.target_type or "task",
                "target_id": request.target_id,
            },
        )


def register_task_assignment_builders(registry: ExportRegistry) -> None:
    for form_id in TASK_ASSIGNMENT_FORM_IDS:
        builder = TaskAssignmentFormBuilder(form_id)
        registry.register(task_assignment_form_key(form_id), builder)
        registry.register(form_id, builder)
        registry.register(task_assignment_form_label(form_id), builder)
