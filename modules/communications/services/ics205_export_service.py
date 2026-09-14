from __future__ import annotations

"""Single entry point for generating the ICS-205 from any button/panel.

Usage from a widget::

    from modules.communications.services.ics205_export_service import generate_ics205

    result = generate_ics205(op_period_id=selected_op_period_id, form_set_id="fema")
    os.startfile(str(result.output_path))
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from modules.forms_creator.exporting import ExportRequest, default_export_service


@dataclass(frozen=True)
class Ics205ExportResult:
    form_id: str
    output_path: Path
    generated_at: str
    op_period_id: Optional[str]


def generate_ics205(
    *,
    incident_id: Optional[str] = None,
    op_period_id: Optional[str] = None,
    form_set_id: Optional[str] = None,
    extra_data: Optional[dict[str, Any]] = None,
) -> Ics205ExportResult:
    """Generate the Incident Radio Communications Plan (ICS-205) PDF.

    Pulls the current channel plan (rows flagged ``include_on_205``) and the
    special instructions saved for ``op_period_id`` (defaults to the active
    operational period). ``form_set_id`` selects the form variant - e.g.
    ``"fema"``, ``"ics_canada"``, ``"uscg"`` - and defaults to the
    configured default set when omitted.
    """
    options: dict[str, Any] = {}
    if op_period_id is not None:
        options["op_period_id"] = op_period_id
    if extra_data:
        options["extra_data"] = extra_data

    result = default_export_service().export(
        ExportRequest(
            form_key="ics_205",
            target_type="communications_plan",
            incident_id=incident_id,
            form_set_id=form_set_id,
            options=options,
        )
    )
    return Ics205ExportResult(
        form_id=result.form_id,
        output_path=result.output_path,
        generated_at=result.generated_at,
        op_period_id=result.metadata.get("op_period_id"),
    )


__all__ = ["Ics205ExportResult", "generate_ics205"]
