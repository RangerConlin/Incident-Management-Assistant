from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from modules.forms_creator.exporting import ExportRequest, default_export_service
from modules.forms_creator.exporting.builders.work_assignments import work_assignment_form_key


@dataclass(frozen=True)
class OutputExportResult:
    output_type: str
    form_id: str
    output_path: Path
    generated_at: str


def generate_work_assignment_output(
    work_assignment_id: int,
    output_type: str,
    *,
    form_set_id: str | None = None,
) -> OutputExportResult:
    result = default_export_service().export(
        ExportRequest(
            form_key=work_assignment_form_key(output_type),
            target_type="work_assignment",
            target_id=work_assignment_id,
            form_set_id=form_set_id,
        )
    )
    return OutputExportResult(
        output_type=str(result.metadata.get("output_type") or output_type),
        form_id=result.form_id,
        output_path=result.output_path,
        generated_at=result.generated_at,
    )
