"""Desktop client service for the canonical ICS-214 activity stream."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schemas import (
    CorrectionCreate,
    EntryCreate,
    EntryFilter,
    ExportRequest,
    LogDefinitionCreate,
    LogDefinitionUpdate,
    VoidRequest,
)


def _client():
    from utils.api_client import api_client
    return api_client


def _json(model) -> dict[str, Any]:
    return model.model_dump(mode="json", exclude_none=True)


def _query(filters: EntryFilter | None) -> dict[str, Any]:
    if filters is None:
        return {}
    params: dict[str, Any] = {}
    names = {
        "person_ids": "person_id", "team_ids": "team_id", "task_ids": "task_id",
        "org_unit_ids": "org_unit_id", "facility_ids": "facility_id",
        "resource_ids": "resource_id", "external_agency_ids": "external_agency_id",
        "sources": "source",
    }
    data = filters.model_dump(mode="json", exclude_none=True)
    for field, value in data.items():
        if value not in (None, [], False):
            params[names.get(field, field)] = value
    if filters.include_voided:
        params["include_voided"] = True
    if filters.unassigned:
        params["unassigned"] = True
    if filters.critical_only:
        params["critical_only"] = True
    if filters.incident_wide is not None:
        params["incident_wide"] = filters.incident_wide
    return params


def create_entry(incident_id: str, data: EntryCreate) -> dict[str, Any]:
    return _client().post(f"/api/incidents/{incident_id}/ics214/entries", json=_json(data))


def list_entries(incident_id: str, filters: EntryFilter | None = None) -> list[dict[str, Any]]:
    return _client().get(f"/api/incidents/{incident_id}/ics214/entries", params=_query(filters))


def association_options(incident_id: str) -> dict[str, list[dict[str, Any]]]:
    return _client().get(f"/api/incidents/{incident_id}/ics214/association-options")


def list_operational_periods(incident_id: str) -> list[dict[str, Any]]:
    return _client().get(f"/api/incidents/{incident_id}/planning/operational-periods")


def void_entry(incident_id: str, entry_id: str, data: VoidRequest) -> dict[str, Any]:
    return _client().post(
        f"/api/incidents/{incident_id}/ics214/entries/{entry_id}/void", json=_json(data)
    )


def correct_entry(incident_id: str, entry_id: str, data: CorrectionCreate) -> dict[str, Any]:
    return _client().post(
        f"/api/incidents/{incident_id}/ics214/entries/{entry_id}/correct", json=_json(data)
    )


def list_log_definitions(incident_id: str) -> list[dict[str, Any]]:
    return _client().get(f"/api/incidents/{incident_id}/ics214/log-definitions")


def create_log_definition(incident_id: str, data: LogDefinitionCreate) -> dict[str, Any]:
    return _client().post(
        f"/api/incidents/{incident_id}/ics214/log-definitions", json=_json(data)
    )


def update_log_definition(
    incident_id: str, definition_id: str, data: LogDefinitionUpdate
) -> dict[str, Any]:
    return _client().patch(
        f"/api/incidents/{incident_id}/ics214/log-definitions/{definition_id}", json=_json(data)
    )


def archive_log_definition(incident_id: str, definition_id: str) -> None:
    _client().delete(f"/api/incidents/{incident_id}/ics214/log-definitions/{definition_id}")


def export_log(incident_id: str, options: ExportRequest):
    """Generate a FEMA ICS-214 PDF from an ad-hoc or saved-view filter."""
    entries = list_entries(incident_id, options.filters)
    if not options.include_auto:
        entries = [entry for entry in entries if entry.get("source") != "auto"]

    incident_name = incident_id
    op_period = None
    try:
        incident = _client().get(f"/api/incidents/{incident_id}/ic-overview")
        incident_name = incident.get("incident_name") or incident.get("name") or incident_id
    except Exception:
        pass
    if options.filters.operational_period_id is not None:
        try:
            op_period = _client().get(
                f"/api/incidents/{incident_id}/planning/operational-periods/"
                f"{options.filters.operational_period_id}"
            )
        except Exception:
            op_period = None

    def _op_value(key: str, fmt: str) -> str:
        if not op_period:
            return ""
        try:
            return datetime.fromisoformat(
                str(op_period.get(key) or "").replace("Z", "+00:00")
            ).strftime(fmt)
        except Exception:
            return ""

    formatted_entries = []
    for entry in entries:
        raw = entry.get("occurred_at") or ""
        try:
            stamp = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).strftime("%m/%d %H%MZ")
        except Exception:
            stamp = str(raw)[:16]
        formatted_entries.append({"timestamp_display": stamp, "text": entry.get("text") or ""})

    resources = []
    try:
        people = {
            int(row["id"]): str(row.get("label") or "")
            for row in association_options(incident_id).get("person_ids", [])
        }
        for person_id in sorted({
            int(person_id)
            for entry in entries
            for person_id in (entry.get("person_ids") or [])
        }):
            resources.append({
                "name": people.get(person_id, f"Person {person_id}"),
                "ics_position": "",
                "home_agency": "",
            })
    except Exception:
        resources = []

    prepared_name = prepared_title = ""
    try:
        from utils.state import AppState
        prepared_name = str(AppState.get_active_user_id() or "")
        prepared_title = str(AppState.get_active_user_role() or "")
    except Exception:
        pass

    base_dir = Path("data") / "uploads" / "ics214" / incident_id
    base_dir.mkdir(parents=True, exist_ok=True)
    file_path = base_dir / f"ICS214_{int(datetime.now(timezone.utc).timestamp())}.pdf"
    assets = Path(__file__).parent / "assets"
    from modules.forms_creator.form_set_registry import FormSetRegistry
    from modules.forms_creator.pdf_filler.pdf_filler import PDFFiller
    form_def = FormSetRegistry().get_form_definition("ics_214")
    PDFFiller(assets / "ics214_mapping.json").fill(
        {
            "incident": {"name": incident_name},
            "op_period": {
                "date_from": _op_value("start_time", "%m/%d/%Y"),
                "date_to": _op_value("end_time", "%m/%d/%Y"),
                "time_from": _op_value("start_time", "%H%MZ"),
                "time_to": _op_value("end_time", "%H%MZ"),
            },
            "unit": {"name": options.unit_name, "ics_position": "", "home_agency": ""},
            "resources": resources,
            "entries": formatted_entries,
            "prepared": {
                "name": prepared_name, "title": prepared_title,
                "dt": datetime.now(timezone.utc).strftime("%m/%d/%Y %H%MZ"),
            },
        },
        assets / "ics214_page1.pdf",
        file_path,
        form_row_groups=form_def.row_groups if form_def else [],
    )

    class ExportResult:
        id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc)
        file_path = str(file_path)

    return ExportResult()
