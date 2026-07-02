"""Shared Intel link and location conventions.

These lightweight types provide a consistent structure for cross-entity
relationships and location/reference data across Intel module records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Linked-record relationship types
# ---------------------------------------------------------------------------

ENTITY_TYPES = [
    "subject",
    "clue",
    "lead",
    "intel_item",
    "task",
    "team",
    "form",
    "gis_feature",
]

RELATIONSHIP_TYPES = [
    "source",
    "related",
    "converted_from",
    "supports",
    "contradicts",
]


@dataclass
class IntelLinkedRecord:
    """A typed reference to another Intel-domain entity.

    Use this for cross-entity links where only the id and entity type
    are stored rather than a full embedded copy of the target.
    """

    entity_type: str           # one of ENTITY_TYPES
    entity_id: str
    relationship: str = "related"   # one of RELATIONSHIP_TYPES
    display_text: Optional[str] = None  # optional cached label

    @classmethod
    def from_dict(cls, data: dict) -> "IntelLinkedRecord":
        return cls(
            entity_type=data.get("entity_type", ""),
            entity_id=data.get("entity_id", ""),
            relationship=data.get("relationship", "related"),
            display_text=data.get("display_text"),
        )

    def to_dict(self) -> dict:
        d: dict = {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "relationship": self.relationship,
        }
        if self.display_text is not None:
            d["display_text"] = self.display_text
        return d


# ---------------------------------------------------------------------------
# Location / reference types
# ---------------------------------------------------------------------------

LOCATION_TYPES = [
    "coordinates",
    "gis_feature",
    "address",
    "description",
]


@dataclass
class IntelLocationRef:
    """A lightweight location or spatial reference.

    Stored on Leads, Intel Items, and Observations.  Use the simplest
    representation that accurately describes where the information applies:
    - ``coordinates``: lat/lon pair
    - ``gis_feature``: reference to a GIS feature by id
    - ``address``: street address or place name
    - ``description``: free-text description when no structured form fits
    """

    type: str = "description"       # one of LOCATION_TYPES
    lat: Optional[float] = None
    lon: Optional[float] = None
    feature_id: Optional[str] = None
    label: Optional[str] = None
    notes: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "IntelLocationRef":
        return cls(
            type=data.get("type", "description"),
            lat=data.get("lat"),
            lon=data.get("lon"),
            feature_id=data.get("feature_id"),
            label=data.get("label"),
            notes=data.get("notes"),
        )

    def to_dict(self) -> dict:
        return {k: v for k, v in {
            "type": self.type,
            "lat": self.lat,
            "lon": self.lon,
            "feature_id": self.feature_id,
            "label": self.label,
            "notes": self.notes,
        }.items() if v is not None}
