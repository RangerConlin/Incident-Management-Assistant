"""Safety Risk Manager hazard register — delegates to the MongoDB API."""

from __future__ import annotations

from typing import Any, Optional

from utils.api_client import api_client

from .models import Hazard, HazardLinks, SpeAssessment

_BODY_FIELDS = (
    "title",
    "description",
    "category",
    "op_period_ids",
    "hazard_zone_ids",
    "location_text",
    "notes",
    "created_by",
    "updated_by",
)


def _spe_from_doc(doc: Optional[dict[str, Any]]) -> Optional[SpeAssessment]:
    if not doc:
        return None
    return SpeAssessment(
        severity=int(doc.get("severity", 1)),
        probability=int(doc.get("probability", 1)),
        exposure=int(doc.get("exposure", 1)),
        score=int(doc.get("score", 0)),
        band=doc.get("band", ""),
        action=doc.get("action", ""),
    )


def _spe_to_payload(assessment: dict[str, Any]) -> dict[str, Any]:
    return {
        "severity": assessment["severity"],
        "probability": assessment["probability"],
        "exposure": assessment["exposure"],
    }


def _links_from_doc(doc: Optional[dict[str, Any]]) -> HazardLinks:
    doc = doc or {}
    return HazardLinks(
        work_assignment_ids=list(doc.get("work_assignment_ids") or []),
        task_ids=list(doc.get("task_ids") or []),
        team_ids=list(doc.get("team_ids") or []),
    )


def _hazard_from_doc(doc: dict[str, Any]) -> Hazard:
    return Hazard(
        id=int(doc.get("id", 0)),
        incident_id=doc.get("incident_id", ""),
        title=doc.get("title", ""),
        description=doc.get("description"),
        category=doc.get("category"),
        hazard_type_id=doc.get("hazard_type_id"),
        hazard_type_text=doc.get("title"),
        source=doc.get("source") or ("library" if doc.get("hazard_type_id") is not None else "incident"),
        op_period_ids=list(doc.get("op_period_ids") or []),
        hazard_zone_ids=list(doc.get("hazard_zone_ids") or []),
        location_text=doc.get("location_text"),
        links=_links_from_doc(doc),
        control_measure="\n".join(doc.get("controls") or []),
        mitigation_text=doc.get("safety_language"),
        ppe_text="\n".join(doc.get("ppe") or []),
        safety_message=doc.get("safety_language"),
        notes=doc.get("notes"),
        default_spe=_spe_from_doc(doc.get("default_spe")),
        spe_residual=_spe_from_doc(doc.get("spe_residual")),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
        created_by=doc.get("created_by"),
        updated_by=doc.get("updated_by"),
    )


def _build_body(payload: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {key: payload[key] for key in _BODY_FIELDS if key in payload}
    if "links" in payload:
        links = payload["links"] or {}
        body["work_assignment_ids"] = list(links.get("work_assignment_ids") or [])
        body["task_ids"] = list(links.get("task_ids") or [])
        body["team_ids"] = list(links.get("team_ids") or [])
    if "hazard_type_id" in payload:
        body["library_hazard_type_id"] = payload["hazard_type_id"]
    if "control_measure" in payload:
        body["controls"] = [line.strip() for line in str(payload["control_measure"] or "").splitlines() if line.strip()]
    if "ppe_text" in payload:
        body["ppe"] = [line.strip() for line in str(payload["ppe_text"] or "").splitlines() if line.strip()]
    if "mitigation_text" in payload:
        body["safety_language"] = str(payload["mitigation_text"] or "")
    elif "safety_message" in payload:
        body["safety_language"] = str(payload["safety_message"] or "")
    if "default_spe" in payload:
        body["default_spe"] = _spe_to_payload(payload["default_spe"]) if payload["default_spe"] else None
    if "spe_residual" in payload:
        body["spe_residual"] = _spe_to_payload(payload["spe_residual"]) if payload["spe_residual"] else None
    return body


def list_hazards(
    incident_id: str,
    *,
    op_period: Optional[int] = None,
    category: Optional[str] = None,
    work_assignment_id: Optional[int] = None,
    hazard_zone_id: Optional[int] = None,
) -> list[Hazard]:
    params: dict[str, Any] = {}
    if op_period is not None:
        params["op_period"] = op_period
    if category:
        params["category"] = category
    if work_assignment_id is not None:
        params["work_assignment_id"] = work_assignment_id
    if hazard_zone_id is not None:
        params["hazard_zone_id"] = hazard_zone_id
    docs = api_client.get(f"/api/incidents/{incident_id}/safety/hazards", params=params) or []
    return [_hazard_from_doc(d) for d in docs]


def get_hazard(incident_id: str, hazard_id: int) -> Hazard:
    doc = api_client.get(f"/api/incidents/{incident_id}/safety/hazards/{hazard_id}")
    return _hazard_from_doc(doc)


def create_hazard(incident_id: str, payload: dict[str, Any]) -> Hazard:
    doc = api_client.post(
        f"/api/incidents/{incident_id}/safety/hazards",
        json=_build_body(payload),
    )
    return _hazard_from_doc(doc)


def update_hazard(incident_id: str, hazard_id: int, payload: dict[str, Any]) -> Hazard:
    doc = api_client.patch(
        f"/api/incidents/{incident_id}/safety/hazards/{hazard_id}",
        json=_build_body(payload),
    )
    return _hazard_from_doc(doc)


def delete_hazard(incident_id: str, hazard_id: int) -> None:
    api_client.delete(f"/api/incidents/{incident_id}/safety/hazards/{hazard_id}")
