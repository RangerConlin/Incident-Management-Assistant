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

SEVERITY_OPTIONS: tuple[tuple[int, str], ...] = (
    (1, "None or slight"),
    (2, "Minimal"),
    (3, "Significant"),
    (4, "Major"),
    (5, "Catastrophic"),
)

PROBABILITY_OPTIONS: tuple[tuple[int, str], ...] = (
    (1, "Impossible or remote"),
    (2, "Unlikely"),
    (3, "About 50-50"),
    (4, "Greater than 50%"),
    (5, "Very likely to happen"),
)

EXPOSURE_OPTIONS: tuple[tuple[int, str], ...] = (
    (1, "None or below average"),
    (2, "Average"),
    (3, "Above average"),
    (4, "Great"),
)

SPE_BANDS: tuple[str, ...] = (
    "Slight",
    "Possible",
    "Substantial",
    "High",
    "Very High",
)


@dataclass(slots=True)
class HazardDefaultSpe:
    """Default SPE profile stored on a master hazard type."""

    severity: int
    probability: int
    exposure: int
    score: int
    band: str
    action: str


@dataclass(slots=True)
class HazardType:
    """Master hazard type definition stored in the master database."""

    name: str
    category: str = "Other"
    description: str = ""
    aliases: list[str] = field(default_factory=list)
    controls: list[str] = field(default_factory=list)
    ppe: list[str] = field(default_factory=list)
    standard_safety_language: str = ""
    default_spe: Optional[HazardDefaultSpe] = None
    active: bool = True
    id: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""
    created_by: str = ""
    updated_by: str = ""


SAFETY_SCENARIO_TYPES: tuple[str, ...] = (
    "General",
    "SAR",
    "Wildfire",
    "Flood",
    "HazMat",
    "Planned Event",
    "Hurricane",
    "Earthquake",
    "Other",
)

SAFETY_TARGET_FORMS: tuple[str, ...] = (
    "ICS-215A",
    "CAPF-160",
    "ICS-208",
    "ORM",
    "ICS-206",
)


@dataclass(slots=True)
class SafetyTemplateHazardEntry:
    """One hazard entry inside a safety analysis template."""

    hazard_type_id: int
    sort_order: int = 0
    override_notes: str = ""
    hazard_name: str = ""
    hazard_category: str = ""
    default_spe_band: str = ""


@dataclass(slots=True)
class SafetyAnalysisTemplate:
    """Named scenario template — a curated set of hazards for a given incident type."""

    name: str
    description: str = ""
    scenario_type: str = "General"
    target_forms: list[str] = field(default_factory=list)
    hazard_entries: list[SafetyTemplateHazardEntry] = field(default_factory=list)
    is_active: bool = True
    notes: str = ""
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
    default_spe_band: str = ""
    matched_on: str = ""
