"""Supplier records pulled from the master database."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(slots=True)
class Supplier:
    id: str
    name: str
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None

    @classmethod
    def from_row(cls, row: Dict[str, object]) -> "Supplier":
        return cls(
            id=row["id"],
            name=row["name"],
            contact_name=row.get("contact_name"),
            phone=row.get("phone"),
            email=row.get("email"),
            address=row.get("address"),
            notes=row.get("notes"),
        )
