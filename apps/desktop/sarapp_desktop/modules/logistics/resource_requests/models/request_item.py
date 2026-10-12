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
        )


def create_item(item_id: str, request_id: str, data: Dict[str, object]) -> RequestItem:
    kind_value = data.get("kind", ItemKind.SUPPLY.value)
    kind = kind_value if isinstance(kind_value, ItemKind) else ItemKind(str(kind_value).upper())
    return RequestItem(
        id=item_id,
        request_id=request_id,
        kind=kind,
        ref_id=data.get("ref_id"),
        description=str(data["description"]),
        quantity=float(data.get("quantity", 1)),
        unit=str(data.get("unit", "unit")),
        special_instructions=data.get("special_instructions"),
    )
