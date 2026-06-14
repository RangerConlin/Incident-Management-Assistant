"""Business rules for CAP ORM processing — delegates to MongoDB API."""

from __future__ import annotations

from dataclasses import asdict
from typing import Iterable, Sequence

from utils.api_client import api_client
from .models import ORMForm, ORMHazard

RISK_LEVELS: Sequence[str] = ("L", "M", "H", "EH")
RISK_ORDER = {level: index for index, level in enumerate(RISK_LEVELS)}

RISK_MATRIX = {
    ("A", "I"): "EH",
    ("A", "II"): "EH",
    ("A", "III"): "EH",
    ("A", "IV"): "H",
    ("A", "V"): "M",
    ("B", "I"): "EH",
    ("B", "II"): "H",
    ("B", "III"): "H",
    ("B", "IV"): "M",
    ("B", "V"): "M",
    ("C", "I"): "H",
    ("C", "II"): "M",
    ("C", "III"): "M",
    ("C", "IV"): "M",
    ("C", "V"): "L",
    ("D", "I"): "M",
    ("D", "II"): "M",
    ("D", "III"): "L",
    ("D", "IV"): "L",
    ("D", "V"): "L",
}


class ApprovalBlockedError(RuntimeError):
    """Raised when approval is attempted while residual risk is too high."""

    def __init__(self, highest: str):
        super().__init__("Approval is blocked until highest residual risk is Medium or Low.")
        self.highest = highest


def risk_from(severity: str, likelihood: str) -> str:
    key = (severity.upper(), likelihood.upper())
    try:
        return RISK_MATRIX[key]
    except KeyError:
        raise ValueError(f"Invalid severity/likelihood combination: {key}")


def _form_from_doc(doc: dict) -> ORMForm:
    return ORMForm(
        id=int(doc.get("id", 0)),
        incident_id=doc.get("incident_id", 0),
        op_period=int(doc.get("op_period", 0)),
        activity=doc.get("activity"),
        prepared_by_id=doc.get("prepared_by_id"),
        date_iso=doc.get("date_iso"),
        highest_residual_risk=doc.get("highest_residual_risk", "L"),
        status=doc.get("status", "draft"),
        approval_blocked=bool(doc.get("approval_blocked", False)),
    )


def _hazard_from_doc(doc: dict) -> ORMHazard:
    return ORMHazard(
        id=int(doc.get("id", 0)),
        form_id=int(doc.get("form_id", 0)),
        sub_activity=doc.get("sub_activity", ""),
        hazard_outcome=doc.get("hazard_outcome", ""),
        initial_risk=doc.get("initial_risk", "L"),
        control_text=doc.get("control_text", ""),
        residual_risk=doc.get("residual_risk", "L"),
        implement_how=doc.get("implement_how"),
        implement_who=doc.get("implement_who"),
    )


def ensure_form(incident_id: int, op_period: int) -> ORMForm:
    doc = api_client.get(
        f"/api/incidents/{incident_id}/safety/orm/form",
        params={"op": op_period},
    )
    return _form_from_doc(doc)


def get_form(incident_id: int, op_period: int) -> ORMForm:
    return ensure_form(incident_id, op_period)


def update_form_header(incident_id: int, op_period: int, payload: dict) -> ORMForm:
    body = {"op_period": op_period}
    for key in ("activity", "prepared_by_id", "date_iso"):
        if key in payload:
            body[key] = payload[key]
    doc = api_client.put(
        f"/api/incidents/{incident_id}/safety/orm/form",
        json=body,
    )
    return _form_from_doc(doc)


def list_hazards(incident_id: int, op_period: int) -> list[ORMHazard]:
    docs = api_client.get(
        f"/api/incidents/{incident_id}/safety/orm/hazards",
        params={"op": op_period},
    ) or []
    return [_hazard_from_doc(d) for d in docs]


def compute_highest_residual(hazards: Iterable[ORMHazard]) -> str:
    highest_index = 0
    for hazard in hazards:
        idx = RISK_ORDER.get(hazard.residual_risk, 0)
        if idx > highest_index:
            highest_index = idx
    return RISK_LEVELS[highest_index]


def add_hazard(incident_id: int, op_period: int, payload: dict) -> ORMHazard:
    body = {
        "op_period": op_period,
        "sub_activity": payload.get("sub_activity", ""),
        "hazard_outcome": payload.get("hazard_outcome", ""),
        "initial_risk": payload.get("initial_risk", "L"),
        "control_text": payload.get("control_text", ""),
        "residual_risk": payload.get("residual_risk", "L"),
        "implement_how": payload.get("implement_how"),
        "implement_who": payload.get("implement_who"),
    }
    doc = api_client.post(
        f"/api/incidents/{incident_id}/safety/orm/hazards",
        json=body,
    )
    return _hazard_from_doc(doc)


def edit_hazard(incident_id: int, op_period: int, hazard_id: int, payload: dict) -> ORMHazard:
    body = {k: v for k, v in payload.items() if k not in ("id", "form_id", "incident_id")}
    doc = api_client.put(
        f"/api/incidents/{incident_id}/safety/orm/hazards/{hazard_id}",
        json=body,
        params={"op": op_period},
    )
    return _hazard_from_doc(doc)


def remove_hazard(incident_id: int, op_period: int, hazard_id: int) -> None:
    api_client.delete(
        f"/api/incidents/{incident_id}/safety/orm/hazards/{hazard_id}",
        params={"op": op_period},
    )


def attempt_approval(incident_id: int, op_period: int) -> ORMForm:
    try:
        doc = api_client.post(
            f"/api/incidents/{incident_id}/safety/orm/approve",
            json={"op_period": op_period},
        )
        return _form_from_doc(doc)
    except Exception as e:
        msg = str(e)
        if "approval_blocked" in msg or "422" in msg:
            form = ensure_form(incident_id, op_period)
            raise ApprovalBlockedError(form.highest_residual_risk)
        raise


def clone_hazards(
    incident_id: int,
    from_op: int,
    to_op: int,
    *,
    clear_residual: bool = True,
) -> list[ORMHazard]:
    src_hazards = list_hazards(incident_id, from_op)
    cloned: list[ORMHazard] = []
    for hazard in src_hazards:
        payload = asdict(hazard)
        if clear_residual:
            payload["residual_risk"] = payload["initial_risk"]
        try:
            cloned.append(add_hazard(incident_id, to_op, payload))
        except Exception:
            pass
    return cloned


def hazard_counts(hazards: Sequence[ORMHazard]) -> dict[str, int]:
    counts = {level: 0 for level in RISK_LEVELS}
    for hazard in hazards:
        if hazard.residual_risk in counts:
            counts[hazard.residual_risk] += 1
    return counts
