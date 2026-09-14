from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from modules.forms_creator.exporting import ExportRequest, default_export_service
from modules.forms_creator.exporting.builders.intel import intel_form_key


@dataclass(frozen=True)
class Sar135ExportResult:
    output_path: Path
    generated_at: str
    clue_id: str


def generate_sar135(
    *,
    clue_id: str,
    incident_id: str | None = None,
    form_set_id: str | None = "sar",
    extra_data: dict[str, Any] | None = None,
) -> Sar135ExportResult:
    result = default_export_service().export(
        ExportRequest(
            form_key=intel_form_key("sar_135"),
            target_type="intel_item",
            target_id=clue_id,
            incident_id=incident_id,
            form_set_id=form_set_id,
            options={"extra_data": extra_data or {}},
        )
    )
    return Sar135ExportResult(
        output_path=result.output_path,
        generated_at=result.generated_at,
        clue_id=str(clue_id),
    )
