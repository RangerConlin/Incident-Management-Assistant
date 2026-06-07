"""Models and constants for the Hazard Type Library."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

HAZARD_CATEGORIES: tuple[str, ...] = (
    "Environmental",
    "Weather",
    "Terrain",
    "Water",
    "Vehicle",
    "Aircraft",
    "Medical",
    "Communications",
    "Infrastructure",
    "Operational",
    "Human Factors",
    "HazMat",
    "Public Safety",
    "Animal/Wildlife",
    "Other",
)

HAZARD_SOURCES: tuple[str, ...] = (
    "AHJ Custom",
    "Imported",
    "FEMA/NIMS",
    "OSHA",
    "Agency Policy",
    "Temporary / Incident Only",
)

HAZARD_RISK_LEVELS: tuple[str, ...] = (
    "Low",
    "Moderate",
    "High",
    "Extreme",
    "Unknown",
)

HAZARD_LIKELIHOODS: tuple[str, ...] = (
    "Rare",
    "Unlikely",
    "Possible",
    "Likely",
    "Almost Certain",
    "Unknown",
)

HAZARD_SEVERITIES: tuple[str, ...] = (
    "Minor",
    "Moderate",
    "Serious",
    "Critical",
    "Catastrophic",
    "Unknown",
)


@dataclass(slots=True)
class HazardMitigation:
    """One reusable mitigation/control measure for a hazard type."""

    hazard_type_id: int
    mitigation_text: str
    mitigation_category: str = ""
    is_default: bool = False
    sort_order: int = 0
    id: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass(slots=True)
class HazardPpeItem:
    """One reusable PPE item for a hazard type."""

    hazard_type_id: int
    ppe_text: str
    is_default: bool = False
    sort_order: int = 0
    id: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass(slots=True)
class HazardReference:
    """Reference material linked to a hazard type."""

    hazard_type_id: int
    title: str
    url_or_path: str = ""
    notes: str = ""
    id: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass(slots=True)
class HazardTypeResourceDefault:
    """Link a hazard type to a resource type that should inherit it by default."""

    hazard_type_id: int
    resource_type_id: int
    notes: str = ""
    resource_type_name: str = ""
    resource_type_category: str = ""
    id: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass(slots=True)
class HazardType:
    """Master hazard type definition stored in the master database."""

    name: str
    display_name: str = ""
    category: str = "Other"
    source: str = "AHJ Custom"
    owner_agency: str = ""
    description: str = ""
    default_risk_level: str = "Unknown"
    default_likelihood: str = "Unknown"
    default_severity: str = "Unknown"
    default_control_measure: str = ""
    default_ppe: str = ""
    default_safety_message: str = ""
    is_active: bool = True
    notes: str = ""
    aliases: list[str] = field(default_factory=list)
    mitigations: list[HazardMitigation] = field(default_factory=list)
    ppe_items: list[HazardPpeItem] = field(default_factory=list)
    references: list[HazardReference] = field(default_factory=list)
    resource_defaults: list[HazardTypeResourceDefault] = field(default_factory=list)
    id: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""
    created_by: str = ""
    updated_by: str = ""


@dataclass(slots=True)
class HazardTypeSearchResult:
    """Lightweight row returned by the smart hazard lookup widget."""

    hazard_type_id: Optional[int]
    hazard_type_text: str
    category: str = ""
    default_risk_level: str = ""
    source: str = ""
    matched_on: str = ""
