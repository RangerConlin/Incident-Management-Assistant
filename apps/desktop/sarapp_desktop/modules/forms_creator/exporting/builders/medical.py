from __future__ import annotations

from typing import Any

from modules.forms_creator.exporting.models import ExportRequest, PreparedExport
from modules.forms_creator.exporting.registry import ExportRegistry
from modules.forms_creator.exporting.service import utcnow_seconds
from utils.api_client import api_client

from .ics import _active_incident_id, _output_path, ics_form_key, ics_form_label


def _active_op_number(incident_id: str, request: ExportRequest) -> int | None:
    raw = request.options.get("op_period")
    if raw in (None, ""):
        raw = request.options.get("op_period_id")
    if raw not in (None, ""):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    try:
        from modules.planning.operational_periods.repository import OperationalPeriodRepository

        active = OperationalPeriodRepository(incident_id).get_active_period()
        number = getattr(active, "number", None) or getattr(active, "id", None)
        return int(number) if number not in (None, "") else None
    except Exception:
        return None


def _get_medical_section(incident_id: str, section: str, op_number: int | None) -> Any:
    endpoint = f"/api/incidents/{incident_id}/medical/ics206/{section}"
    params = {"op": op_number} if op_number is not None else None
    return api_client.get(endpoint, params=params)


def _map_aid_station(row: dict[str, Any]) -> dict[str, Any]:
    from modules.forms_creator.context import _infer_paramedics_on_site

    return {
        "id": row.get("id") or "",
        "op_period": row.get("op_period") or "",
        "name": row.get("name") or "",
        "type": row.get("type") or "",
        "level": row.get("level") or "",
        "contact_frequency": row.get("contact_frequency") or "",
        "facility_id": row.get("facility_id") or "",
        "location_text": row.get("location_text") or "",
        "latitude": row.get("latitude"),
        "longitude": row.get("longitude"),
        "is_24_7": bool(row.get("is_24_7")),
        "paramedics_on_site": _infer_paramedics_on_site(row),
        "manager_name": row.get("manager_name") or "",
        "notes": row.get("notes") or "",
    }


def _map_ambulance_service(row: dict[str, Any]) -> dict[str, Any]:
    from modules.forms_creator.context import _coerce_service_level

    service_level = _coerce_service_level(row)
    return {
        "id": row.get("id") or "",
        "op_period": row.get("op_period") or "",
        "name": row.get("name") or "",
        "type": row.get("type") or "",
        "service_level": service_level,
        "service_level_label": {0: "Other", 1: "BLS", 2: "ALS"}.get(service_level, "Other"),
        "phone": row.get("phone") or "",
        "location": row.get("location") or "",
        "notes": row.get("notes") or "",
    }


def _map_hospital(row: dict[str, Any]) -> dict[str, Any]:
    from modules.forms_creator.context import FormDataContext

    return FormDataContext()._normalize_hospital_row(row)


class Ics206FormBuilder:
    """Prepares the Medical Plan (ICS-206) from op-scoped medical sections."""

    form_id = "ics_206"

    def build(self, request: ExportRequest) -> PreparedExport:
        incident_id = _active_incident_id(request)
        op_number = _active_op_number(incident_id, request)
        generated_at = utcnow_seconds()

        aid_stations = _get_medical_section(incident_id, "aid-stations", op_number) or []
        ambulance_services = _get_medical_section(incident_id, "ambulance-services", op_number) or []
        hospitals = _get_medical_section(incident_id, "hospitals", op_number) or []

        extra_data: dict[str, Any] = {
            "ics_206_aid_stations": [_map_aid_station(row) for row in aid_stations],
            "ics_206_ambulance_services": [
                _map_ambulance_service(row) for row in ambulance_services
            ],
            "ics_206_hospitals": [_map_hospital(row) for row in hospitals],
            "ics_206_air_ambulance": _get_medical_section(incident_id, "air-ambulance", op_number) or [],
            "ics_206_medical_comms": _get_medical_section(incident_id, "comms", op_number) or [],
            "ics_206_procedures": _get_medical_section(incident_id, "procedures", op_number) or {},
            "ics_206_signatures": _get_medical_section(incident_id, "signatures", op_number) or {},
        }
        manual = request.options.get("extra_data")
        if isinstance(manual, dict):
            extra_data = {**extra_data, **manual}

        return PreparedExport(
            form_id=self.form_id,
            output_path=_output_path(self.form_id, request, generated_at),
            incident_id=incident_id,
            form_set_id=request.form_set_id,
            extra_data=extra_data,
            metadata={
                "generated_at": generated_at,
                "form_label": ics_form_label(self.form_id),
                "builder_level": "ics_206",
                "data_domain": "medical_plan",
                "op_period": op_number,
                "target_type": request.target_type or "medical_plan",
                "target_id": request.target_id,
            },
        )


def register_medical_builders(registry: ExportRegistry) -> None:
    builder = Ics206FormBuilder()
    registry.register(ics_form_key(builder.form_id), builder)
    registry.register(builder.form_id, builder)
    registry.register(ics_form_label(builder.form_id), builder)
    registry.register("medical_plan", builder)
