from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class SpatialFeatureLink:
    id: int | None
    incident_id: str
    feature_id: int
    linked_module: str
    linked_record_type: str
    linked_record_id: str
    relationship_type: str
    created_at: datetime | None
