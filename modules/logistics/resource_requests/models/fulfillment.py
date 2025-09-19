"""Fulfillment dataclass."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .enums import FulfillmentStatus


@dataclass(slots=True)
class FulfillmentRecord:
    id: str
    request_id: str
    status: FulfillmentStatus
    ts_utc: str
    supplier_id: Optional[str] = None
    assigned_team_id: Optional[str] = None
    assigned_vehicle_id: Optional[str] = None
    eta_utc: Optional[str] = None
    note: Optional[str] = None

    def to_row(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "supplier_id": self.supplier_id,
            "assigned_team_id": self.assigned_team_id,
            "assigned_vehicle_id": self.assigned_vehicle_id,
            "eta_utc": self.eta_utc,
            "status": self.status.value,
            "note": self.note,
            "ts_utc": self.ts_utc,
        }

    @classmethod
    def from_row(cls, row: Dict[str, object]) -> "FulfillmentRecord":
        return cls(
            id=row["id"],
            request_id=row["request_id"],
            supplier_id=row.get("supplier_id"),
            assigned_team_id=row.get("assigned_team_id"),
            assigned_vehicle_id=row.get("assigned_vehicle_id"),
            eta_utc=row.get("eta_utc"),
            status=FulfillmentStatus(row["status"]),
            note=row.get("note"),
            ts_utc=row["ts_utc"],
        )
