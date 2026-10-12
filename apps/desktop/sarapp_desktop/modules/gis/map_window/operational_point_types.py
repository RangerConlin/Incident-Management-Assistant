"""Catalog of point types that operators may place directly on the map."""

from __future__ import annotations

from dataclasses import dataclass

from modules.gis.models.feature_types import FeatureCategory, FeatureType


@dataclass(frozen=True, slots=True)
class OperationalPointType:
    """User-facing metadata for a manually placeable spatial point."""

    feature_type: FeatureType
    category: FeatureCategory
    display_name: str
    short_label: str | None = None
    primary: bool = False


OPERATIONAL_POINT_TYPES: tuple[OperationalPointType, ...] = (
    OperationalPointType(
        FeatureType.LANDING_ZONE,
        FeatureCategory.LOGISTICS,
        "Landing Zone",
        "LZ",
        True,
    ),
    OperationalPointType(
        FeatureType.CHECK_IN_POINT,
        FeatureCategory.COMMUNICATIONS,
        "Access / Check-in Point",
        "Access Pt",
        True,
    ),
    OperationalPointType(
        FeatureType.ROADBLOCK,
        FeatureCategory.OPERATIONS,
        "Roadblock",
        "Roadblock",
        True,
    ),
    OperationalPointType(
        FeatureType.MED_UNIT_LOCATION,
        FeatureCategory.LOGISTICS,
        "Medical Unit",
        "Medical",
        True,
    ),
    OperationalPointType(
        FeatureType.REPEATER_SITE,
        FeatureCategory.COMMUNICATIONS,
        "Communications Site",
        "Comms Site",
        True,
    ),
    OperationalPointType(FeatureType.HELISPOT, FeatureCategory.LOGISTICS, "Helispot"),
    OperationalPointType(FeatureType.STAGING_AREA, FeatureCategory.LOGISTICS, "Staging Area"),
    OperationalPointType(FeatureType.BASE_CAMP, FeatureCategory.LOGISTICS, "Base Camp"),
    OperationalPointType(FeatureType.VEHICLE_LOCATION, FeatureCategory.LOGISTICS, "Vehicle Location"),
    OperationalPointType(FeatureType.CLUE, FeatureCategory.INTEL, "Clue"),
    OperationalPointType(FeatureType.SIGHTING, FeatureCategory.INTEL, "Sighting"),
    OperationalPointType(FeatureType.SUBJECT_LKP, FeatureCategory.INTEL, "Subject Last Known Point"),
    OperationalPointType(FeatureType.SUBJECT_PLS, FeatureCategory.INTEL, "Subject Place Last Seen"),
    OperationalPointType(
        FeatureType.SUBJECT_EVENT_LOCATION,
        FeatureCategory.INTEL,
        "Subject Event Location",
    ),
    OperationalPointType(FeatureType.INTERVIEW_LOCATION, FeatureCategory.INTEL, "Interview Location"),
    OperationalPointType(FeatureType.EVIDENCE_LOCATION, FeatureCategory.INTEL, "Evidence Location"),
    OperationalPointType(FeatureType.HAZARD_ZONE, FeatureCategory.SAFETY, "Hazard"),
)


def operational_point_type(feature_type: FeatureType | str) -> OperationalPointType:
    resolved = feature_type if isinstance(feature_type, FeatureType) else FeatureType(feature_type)
    for definition in OPERATIONAL_POINT_TYPES:
        if definition.feature_type is resolved:
            return definition
    raise KeyError(resolved.value)


def primary_operational_point_types() -> tuple[OperationalPointType, ...]:
    return tuple(definition for definition in OPERATIONAL_POINT_TYPES if definition.primary)
