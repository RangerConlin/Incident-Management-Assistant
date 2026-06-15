from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


DEFAULT_APPROVAL_STEPS = [
    "Submitted",
    "Reviewed",
    "Approved",
    "Paid/Reimbursed",
    "Closed",
]


def get_chain(session: Session, chain_id: int | None = None) -> List[str]:
    del session, chain_id
    return list(DEFAULT_APPROVAL_STEPS)


def next_step(chain: List[str], completed: List[str]) -> Optional[str]:
    for step in chain:
        if step not in completed:
            return step
    return None


def record_approval(
    session: Session,
    incident_id: str,
    entity: str,
    entity_id: int,
    step: str,
    actor_id: str | int | None,
    action: str,
    comments: Optional[str] = None,
) -> None:
    session.execute(
        text(
            """
            INSERT INTO finance_approvals
            (incident_id, record_type, record_id, approver_id, approver_role, action, timestamp, comments)
            VALUES (:incident_id, :record_type, :record_id, :approver_id, :approver_role, :action, :timestamp, :comments)
            """
        ),
        {
            "incident_id": incident_id,
            "record_type": entity,
            "record_id": entity_id,
            "approver_id": None if actor_id is None else str(actor_id),
            "approver_role": step,
            "action": action,
            "timestamp": datetime.utcnow(),
            "comments": comments,
        },
    )
    session.commit()

