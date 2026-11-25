"""Resource request item model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .enums import ItemKind


@dataclass(slots=True)
class RequestItem:
    id: str
    request_id: str
    kind: ItemKind
    description: str
    quantity: float
    unit: str
    ref_id: Optional[str] = None
    special_instructions: Optional[str] = None
    # Finance/Admin cost-impact fields. estimated_unit_cost/estimated_total_cost
    # are set when the request has a cost impact; estimate_id links to the
    # Estimate record Finance/Admin created or committed for this item (see
    # docs/archive/design-documents/Instructions/finance_architecture.md).
    estimated_unit_cost: Optional[float] = None
    estimated_total_cost: Optional[float] = None
    estimate_id: Optional[int] = None

    def to_row(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "kind": self.kind.value,
            "ref_id": self.ref_id,
            "description": self.description,
            "quantity": self.quantity,
            "unit": self.unit,
            "special_instructions": self.special_instructions,
            "estimated_unit_cost": self.estimated_unit_cost,
            "estimated_total_cost": self.estimated_total_cost,
            "estimate_id": self.estimate_id,
        }

    @classmethod
    def from_row(cls, row: Dict[str, object]) -> "RequestItem":
        return cls(
            id=row["id"],
            request_id=row["request_id"],
            kind=ItemKind(row["kind"]),
            ref_id=row.get("ref_id"),
            description=row["description"],
            quantity=float(row["quantity"]),
            unit=row["unit"],
            special_instructions=row.get("special_instructions"),
            estimated_unit_cost=(
                float(row["estimated_unit_cost"]) if row.get("estimated_unit_cost") is not None else None
            ),
            estimated_total_cost=(
                float(row["estimated_total_cost"]) if row.get("estimated_total_cost") is not None else None
            ),
            estimate_id=(int(row["estimate_id"]) if row.get("estimate_id") is not None else None),
        )


def create_item(item_id: str, request_id: str, data: Dict[str, object]) -> RequestItem:
    kind_value = data.get("kind", ItemKind.SUPPLY.value)
    kind = kind_value if isinstance(kind_value, ItemKind) else ItemKind(str(kind_value).upper())
    estimated_unit_cost = data.get("estimated_unit_cost")
    estimated_total_cost = data.get("estimated_total_cost")
    return RequestItem(
        id=item_id,
        request_id=request_id,
        kind=kind,
        ref_id=data.get("ref_id"),
        description=str(data["description"]),
        quantity=float(data.get("quantity", 1)),
        unit=str(data.get("unit", "unit")),
        special_instructions=data.get("special_instructions"),
        estimated_unit_cost=float(estimated_unit_cost) if estimated_unit_cost is not None else None,
        estimated_total_cost=float(estimated_total_cost) if estimated_total_cost is not None else None,
        estimate_id=int(data["estimate_id"]) if data.get("estimate_id") is not None else None,
    )
