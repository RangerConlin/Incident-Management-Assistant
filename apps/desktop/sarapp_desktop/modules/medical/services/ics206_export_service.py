from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from modules.forms_creator.exporting import ExportRequest
from modules.forms_creator.exporting.service import default_export_service


@dataclass(frozen=True)
class Ics206ExportResult:
    output_path: Path
    generated_at: str
    metadata: dict


def generate_ics206(
    *,
    incident_id: str | None = None,
    op_period: int | None = None,
    form_set_id: str | None = None,
) -> Ics206ExportResult:
    options = {}
    if op_period is not None:
        options["op_period"] = op_period
    result = default_export_service().export(
        ExportRequest(
            form_key="ics_206",
            incident_id=incident_id,
            form_set_id=form_set_id,
            target_type="medical_plan",
            target_id=op_period,
            options=options,
        )
    )
    return Ics206ExportResult(
        output_path=result.output_path,
        generated_at=result.generated_at,
        metadata=result.metadata,
    )
