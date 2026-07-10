"""Safety Risk Manager hazard register — delegates to the MongoDB API."""

from __future__ import annotations

from typing import Any, Optional

from utils.api_client import api_client

from .models import Hazard, HazardLinks, SpeAssessment

_BODY_FIELDS = (
    "title",
    "description",
    "category",
    "hazard_type_id",
    "hazard_type_text",
    "source",
    "op_period_ids",
    "location_text",
    "control_measure",
    "mitigation_text",
    "ppe_text",
    "safety_message",
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
        hazard_type_text=doc.get("hazard_type_text"),
        source=doc.get("source"),
        op_period_ids=list(doc.get("op_period_ids") or []),
        location_text=doc.get("location_text"),
        links=_links_from_doc(doc.get("links")),
        control_measure=doc.get("control_measure"),
        mitigation_text=doc.get("mitigation_text"),
        ppe_text=doc.get("ppe_text"),
        safety_message=doc.get("safety_message"),
        notes=doc.get("notes"),
        spe_initial=_spe_from_doc(doc.get("spe_initial")),
        spe_residual=_spe_from_doc(doc.get("spe_residual")),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
        created_by=doc.get("created_by"),
        updated_by=doc.get("updated_by"),
    )


def _build_body(payload: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {key: payload[key] for key in _BODY_FIELDS if key in payload}
    if "links" in payload:
        body["links"] = payload["links"]
    if "spe_initial" in payload:
        body["spe_initial"] = _spe_to_payload(payload["spe_initial"]) if payload["spe_initial"] else None
    if "spe_residual" in payload:
        body["spe_residual"] = _spe_to_payload(payload["spe_residual"]) if payload["spe_residual"] else None
    return body


def list_hazards(
    incident_id: str,
    *,
    op_period: Optional[int] = None,
    category: Optional[str] = None,
    work_assignment_id: Optional[int] = None,
) -> list[Hazard]:
    params: dict[str, Any] = {}
    if op_period is not None:
        params["op_period"] = op_period
    if category:
        params["category"] = category
    if work_assignment_id is not None:
        params["work_assignment_id"] = work_assignment_id
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
