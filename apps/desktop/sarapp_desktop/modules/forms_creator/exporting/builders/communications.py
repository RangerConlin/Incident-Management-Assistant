from __future__ import annotations

from typing import Any, Optional

from modules.forms_creator.exporting.models import ExportRequest, PreparedExport
from modules.forms_creator.exporting.registry import ExportRegistry
from modules.forms_creator.exporting.service import utcnow_seconds
from utils.api_client import api_client

from .ics import _active_incident_id, _output_path, ics_form_key, ics_form_label


def _active_op_period_id(incident_id: str, request: ExportRequest) -> Optional[str]:
    op_period_id = request.options.get("op_period_id")
    if op_period_id not in (None, ""):
        return str(op_period_id)
    try:
        from modules.planning.operational_periods.repository import OperationalPeriodRepository

        active = OperationalPeriodRepository(incident_id).get_active_period()
        return str(active.id) if active else None
    except Exception:
        return None


def _map_channel_row(row: dict[str, Any]) -> dict[str, Any]:
    assignment = " / ".join(
        part for part in (row.get("assignment_division"), row.get("assignment_team")) if part
    )
    return {
        "id": row.get("id") or "",
        "band": row.get("band") or "",
        "function": row.get("function") or "",
        "name": row.get("channel") or row.get("name") or "",
        "system_type": row.get("system") or "",
        "assignment": assignment,
        "assignment_division": row.get("assignment_division") or "",
        "assignment_team": row.get("assignment_team") or "",
        "rx_freq": row.get("rx_freq") or "",
        "rx_tone": row.get("rx_tone") or "",
        "tx_freq": row.get("tx_freq") or "",
        "tx_tone": row.get("tx_tone") or "",
        "mode": row.get("mode") or "",
        "encryption": row.get("encryption") or "",
        "priority": row.get("priority") or "",
        "remarks": row.get("remarks") or "",
    }


class Ics205FormBuilder:
    """Prepares the Incident Radio Communications Plan (ICS-205) export.

    Pulls the live channel plan (filtered to rows flagged
    ``include_on_205``) and the special instructions saved for the selected
    operational period, so the exported PDF matches what is shown in the
    ICS-205 editor (``modules.communications.panels.ics205_window``) rather
    than the unfiltered/unscoped defaults the generic ICS form builder would
    fall back to.

    One builder serves every registered ICS-205 form set (FEMA, ICS Canada,
    USCG) - they all read the same ``channels``/``channels_notes`` data keys
    and only differ in ``mapping.json`` field layout, which is resolved by
    ``form_set_id`` at generation time.
    """

    form_id = "ics_205"

    def build(self, request: ExportRequest) -> PreparedExport:
        incident_id = _active_incident_id(request)
        op_period_id = _active_op_period_id(incident_id, request)

        rows = api_client.get(f"/api/incidents/{incident_id}/channels-plan") or []
        rows = sorted(rows, key=lambda r: (r.get("sort_index") or 0, r.get("channel_id") or ""))
        channels = [_map_channel_row(r) for r in rows if r.get("include_on_205", True)]

        plan = api_client.get(
            f"/api/incidents/{incident_id}/communications-plan",
            params={"op_period_id": op_period_id} if op_period_id is not None else None,
        ) or {}
        channels_notes = plan.get("special_instructions") or ""

        extra_data: dict[str, Any] = {
            "channels": channels,
            "channels_notes": channels_notes,
        }
        manual = request.options.get("extra_data")
        if isinstance(manual, dict):
            extra_data = {**extra_data, **manual}

        generated_at = utcnow_seconds()
        output_path = _output_path(self.form_id, request, generated_at)

        return PreparedExport(
            form_id=self.form_id,
            output_path=output_path,
            incident_id=incident_id,
            form_set_id=request.form_set_id,
            extra_data=extra_data,
            metadata={
                "generated_at": generated_at,
                "form_label": ics_form_label(self.form_id),
                "builder_level": "ics_205",
                "data_domain": "communications_plan",
                "op_period_id": op_period_id,
                "target_type": request.target_type or "communications_plan",
                "target_id": request.target_id,
            },
        )


def register_communications_builders(registry: ExportRegistry) -> None:
    builder = Ics205FormBuilder()
    registry.register(ics_form_key(builder.form_id), builder)
    registry.register(builder.form_id, builder)
    registry.register(ics_form_label(builder.form_id), builder)
    registry.register("communications_plan", builder)
