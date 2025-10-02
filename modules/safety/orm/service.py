"""Business rules for CAP ORM processing."""

from __future__ import annotations

from dataclasses import asdict
from typing import Iterable, Sequence

from utils.audit import now_utc_iso

from .models import ORMForm, ORMHazard
from . import repository

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


def ensure_form(incident_id: int, op_period: int) -> ORMForm:
    with repository.incident_connection(incident_id) as conn:
        form = repository.fetch_form(conn, incident_id, op_period)
        if form is None:
            form = repository.insert_form(conn, incident_id, op_period)
        return form


def get_form(incident_id: int, op_period: int) -> ORMForm:
    with repository.incident_connection(incident_id) as conn:
        form = repository.fetch_form(conn, incident_id, op_period)
        if form is None:
            raise KeyError("Form not found")
        return form


def update_form_header(incident_id: int, op_period: int, payload: dict) -> ORMForm:
    with repository.incident_connection(incident_id) as conn:
        form = repository.fetch_form(conn, incident_id, op_period)
        if form is None:
            form = repository.insert_form(conn, incident_id, op_period)
        updates = {}
        for key in ("activity", "prepared_by_id", "date_iso"):
            if key in payload:
                updates[key] = payload[key]
        return repository.update_form_fields(conn, form.id, updates)


def list_hazards(incident_id: int, op_period: int) -> list[ORMHazard]:
    with repository.incident_connection(incident_id) as conn:
        form = repository.fetch_form(conn, incident_id, op_period)
        if form is None:
            form = repository.insert_form(conn, incident_id, op_period)
        return repository.list_hazards(conn, form.id)


def compute_highest_residual(hazards: Iterable[ORMHazard]) -> str:
    highest_index = 0
    for hazard in hazards:
        level = hazard.residual_risk
        idx = RISK_ORDER.get(level, 0)
        if idx > highest_index:
            highest_index = idx
    return RISK_LEVELS[highest_index]


def _recompute_state(conn, form: ORMForm) -> ORMForm:
    hazards = repository.list_hazards(conn, form.id)
    highest = compute_highest_residual(hazards)
    blocked = highest in {"H", "EH"}
    if blocked:
        status = "pending_mitigation"
    else:
        status = form.status
        if status == "pending_mitigation":
            status = "draft"
    return repository.update_form_state(
        conn,
        form_id=form.id,
        highest_residual_risk=highest,
        status=status,
        approval_blocked=blocked,
    )


def add_hazard(incident_id: int, op_period: int, payload: dict) -> ORMHazard:
    with repository.incident_connection(incident_id) as conn:
        form = repository.fetch_form(conn, incident_id, op_period)
        if form is None:
            form = repository.insert_form(conn, incident_id, op_period)
        payload = dict(payload)
        payload["incident_id"] = incident_id
        hazard = repository.insert_hazard(conn, form.id, payload)
        _recompute_state(conn, form)
        return hazard


def edit_hazard(incident_id: int, op_period: int, hazard_id: int, payload: dict) -> ORMHazard:
    with repository.incident_connection(incident_id) as conn:
        form = repository.fetch_form(conn, incident_id, op_period)
        if form is None:
            raise KeyError("form not found")
        updated = repository.update_hazard(conn, hazard_id, payload)
        form = repository.fetch_form_by_id(conn, form.id)
        assert form is not None
        _recompute_state(conn, form)
        return updated


def remove_hazard(incident_id: int, op_period: int, hazard_id: int) -> None:
    with repository.incident_connection(incident_id) as conn:
        form = repository.fetch_form(conn, incident_id, op_period)
        if form is None:
            raise KeyError("form not found")
        repository.delete_hazard(conn, hazard_id)
        form = repository.fetch_form_by_id(conn, form.id)
        assert form is not None
        _recompute_state(conn, form)


def attempt_approval(incident_id: int, op_period: int) -> ORMForm:
    with repository.incident_connection(incident_id) as conn:
        form = repository.fetch_form(conn, incident_id, op_period)
        if form is None:
            form = repository.insert_form(conn, incident_id, op_period)
        form = _recompute_state(conn, form)
        if form.approval_blocked:
            repository.log_audit(
                conn,
                incident_id=incident_id,
                entity="orm_form",
                entity_id=form.id,
                action="approval_attempt_blocked",
                field="highest_residual_risk",
                old_value=form.highest_residual_risk,
                new_value=form.highest_residual_risk,
            )
            raise ApprovalBlockedError(form.highest_residual_risk)
        updates = {"status": "approved"}
        if not form.date_iso:
            updates["date_iso"] = now_utc_iso()
        updated = repository.update_form_fields(conn, form.id, updates)
        return repository.update_form_state(
            conn,
            form_id=updated.id,
            highest_residual_risk=updated.highest_residual_risk,
            status=updated.status,
            approval_blocked=False,
        )


def clone_hazards(
    incident_id: int,
    from_op: int,
    to_op: int,
    *,
    clear_residual: bool = True,
) -> list[ORMHazard]:
    with repository.incident_connection(incident_id) as conn:
        src_form = repository.fetch_form(conn, incident_id, from_op)
        if src_form is None:
            return []
        dst_form = repository.fetch_form(conn, incident_id, to_op)
        if dst_form is None:
            dst_form = repository.insert_form(conn, incident_id, to_op)
        hazards = repository.list_hazards(conn, src_form.id)
        cloned: list[ORMHazard] = []
        for hazard in hazards:
            payload = asdict(hazard)
            payload.pop("id")
            payload.pop("form_id")
            if clear_residual:
                payload["residual_risk"] = payload["initial_risk"]
            repository_payload = dict(payload)
            repository_payload["incident_id"] = incident_id
            cloned.append(repository.insert_hazard(conn, dst_form.id, repository_payload))
        _recompute_state(conn, dst_form)
        return cloned


def hazard_counts(hazards: Sequence[ORMHazard]) -> dict[str, int]:
    counts = {level: 0 for level in RISK_LEVELS}
    for hazard in hazards:
        if hazard.residual_risk in counts:
            counts[hazard.residual_risk] += 1
    return counts
