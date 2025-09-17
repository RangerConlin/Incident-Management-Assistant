"""Approval record dataclass."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .enums import ApprovalAction


@dataclass(slots=True)
class ApprovalRecord:
    id: str
    request_id: str
    action: ApprovalAction
    actor_id: str
    ts_utc: str
    note: Optional[str] = None

    def to_row(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "action": self.action.value,
            "actor_id": self.actor_id,
            "note": self.note,
            "ts_utc": self.ts_utc,
        }

    @classmethod
    def from_row(cls, row: Dict[str, object]) -> "ApprovalRecord":
        return cls(
            id=row["id"],
            request_id=row["request_id"],
            action=ApprovalAction(row["action"]),
            actor_id=row["actor_id"],
            note=row.get("note"),
            ts_utc=row["ts_utc"],
        )
