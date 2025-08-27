from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_chain(session: Session, chain_id: int) -> List[str]:
    row = session.execute(
        text("SELECT steps_json FROM approval_chains WHERE id=:id"),
        {"id": chain_id},
    ).fetchone()
    if not row:
        return []
    return json.loads(row[0])


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
    actor_id: int,
    action: str,
    comments: Optional[str] = None,
) -> None:
    session.execute(
        text(
            """
            INSERT INTO approvals
            (incident_id, entity, entity_id, step, actor_id, action, timestamp, comments)
            VALUES (:incident_id, :entity, :entity_id, :step, :actor_id, :action, :timestamp, :comments)
            """
        ),
        {
            "incident_id": incident_id,
            "entity": entity,
            "entity_id": entity_id,
            "step": step,
            "actor_id": actor_id,
            "action": action,
            "timestamp": datetime.utcnow(),
            "comments": comments,
        },
    )
    session.commit()
