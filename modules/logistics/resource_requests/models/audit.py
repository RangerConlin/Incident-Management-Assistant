"""Audit trail helper dataclass."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(slots=True)
class AuditRecord:
    id: str
    entity_type: str
    entity_id: str
    field: str
    ts_utc: str
    new_value: Optional[str] = None
    old_value: Optional[str] = None
    actor_id: Optional[str] = None

    def to_row(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "actor_id": self.actor_id,
            "field": self.field,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "ts_utc": self.ts_utc,
        }

    @classmethod
    def from_row(cls, row: Dict[str, object]) -> "AuditRecord":
        return cls(
            id=row["id"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            actor_id=row.get("actor_id"),
            field=row["field"],
            old_value=row.get("old_value"),
            new_value=row.get("new_value"),
            ts_utc=row["ts_utc"],
        )
