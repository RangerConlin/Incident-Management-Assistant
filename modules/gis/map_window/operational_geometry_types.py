"""Catalog of line and area types that operators may draw directly on the map.

Counterpart of ``operational_point_types``. Generated products (search grids,
team/aircraft tracks) are intentionally absent: they come from generators or
live feeds, not from click-by-click drawing.
"""

from __future__ import annotations

from dataclasses import dataclass

from modules.gis.models.feature_types import FeatureCategory, FeatureType
from modules.gis.models.geometry_types import GeometryType


@dataclass(frozen=True, slots=True)
class OperationalGeometryType:
    """User-facing metadata for a manually drawable line or area."""

    feature_type: FeatureType
    geometry_type: GeometryType
    category: FeatureCategory
    display_name: str
    short_label: str | None = None
    primary: bool = False
    # Planned-event symbology: the subtype refines the feature type and is
    # also the style key (see symbology.py); menu_section groups ribbon menus.
    subtype: str | None = None
    style_key: str | None = None
    menu_section: str | None = None


OPERATIONAL_LINE_TYPES: tuple[OperationalGeometryType, ...] = (
    OperationalGeometryType(
        FeatureType.CONTAINMENT_LINE,
        GeometryType.LINE,
        FeatureCategory.OPERATIONS,
        "Containment Line",
        "Containment",
        True,
    ),
    OperationalGeometryType(
        FeatureType.ROUTE,
        GeometryType.LINE,
        FeatureCategory.OPERATIONS,
        "Route",
        "Route",
        True,
    ),
    OperationalGeometryType(
        FeatureType.TASK_ROUTE,
        GeometryType.LINE,
        FeatureCategory.OPERATIONS,
        "Task Route",
        "Task Route",
        True,
    ),
    OperationalGeometryType(
        FeatureType.SUBJECT_INTENDED_ROUTE,
        GeometryType.LINE,
        FeatureCategory.INTEL,
        "Subject Intended Route",
    ),
)

OPERATIONAL_AREA_TYPES: tuple[OperationalGeometryType, ...] = (
    OperationalGeometryType(
        FeatureType.TASK_AREA,
        GeometryType.POLYGON,
        FeatureCategory.OPERATIONS,
        "Task Area",
        "Task Area",
        True,
    ),
    OperationalGeometryType(
        FeatureType.ASSIGNMENT_AREA,
        GeometryType.POLYGON,
        FeatureCategory.OPERATIONS,
        "Assignment Area",
        "Assignment",
        True,
    ),
    OperationalGeometryType(
        FeatureType.SEARCH_SEGMENT,
        GeometryType.POLYGON,
        FeatureCategory.OPERATIONS,
        "Search Segment",
        "Segment",
        True,
    ),
    OperationalGeometryType(
        FeatureType.NO_ENTRY_ZONE,
        GeometryType.POLYGON,
        FeatureCategory.SAFETY,
        "No-Entry Zone",
        "No Entry",
        True,
    ),
    OperationalGeometryType(
        FeatureType.CLOSURE_AREA,
        GeometryType.POLYGON,
        FeatureCategory.SAFETY,
        "Closure Area",
        "Closure",
        True,
    ),
    OperationalGeometryType(
        FeatureType.OPERATIONAL_BOUNDARY,
        GeometryType.POLYGON,
        FeatureCategory.PLANNING,
        "Operational Boundary",
    ),
    OperationalGeometryType(
        FeatureType.RADIO_DEAD_ZONE,
        GeometryType.POLYGON,
        FeatureCategory.COMMUNICATIONS,
        "Radio Dead Zone",
    ),
    OperationalGeometryType(FeatureType.HAZARD_ZONE, GeometryType.POLYGON, FeatureCategory.SAFETY, "Hazard Area"),
    OperationalGeometryType(FeatureType.STAGING_AREA, GeometryType.POLYGON, FeatureCategory.LOGISTICS, "Staging Area"),
    OperationalGeometryType(FeatureType.BASE_CAMP, GeometryType.POLYGON, FeatureCategory.LOGISTICS, "Base Camp Area"),
    OperationalGeometryType(
        FeatureType.LANDING_ZONE,
        GeometryType.POLYGON,
        FeatureCategory.LOGISTICS,
        "Landing Zone Area",
    ),
)

# Planned-event symbology (first pass): each entry reuses an existing feature
# type and is distinguished by subtype/style_key, not by a new FeatureType.
OPERATIONAL_EVENT_LINE_TYPES: tuple[OperationalGeometryType, ...] = (
    OperationalGeometryType(
        FeatureType.ROUTE,
        GeometryType.LINE,
        FeatureCategory.OPERATIONS,
        "Primary Event Route",
        subtype="primary_event_route",
        style_key="primary_event_route",
        menu_section="Event Routes",
    ),
    OperationalGeometryType(
        FeatureType.ROUTE,
        GeometryType.LINE,
        FeatureCategory.OPERATIONS,
        "Alternate Event Route",
        subtype="alternate_event_route",
        style_key="alternate_event_route",
        menu_section="Event Routes",
    ),
    OperationalGeometryType(
        FeatureType.ROUTE,
        GeometryType.LINE,
        FeatureCategory.OPERATIONS,
        "Pedestrian Flow",
        subtype="pedestrian_flow",
        style_key="pedestrian_flow",
        menu_section="Event Routes",
    ),
    OperationalGeometryType(
        FeatureType.ROUTE,
        GeometryType.LINE,
        FeatureCategory.OPERATIONS,
        "Vehicle Flow",
        subtype="vehicle_flow",
        style_key="vehicle_flow",
        menu_section="Event Routes",
    ),
    OperationalGeometryType(
        FeatureType.ROUTE,
        GeometryType.LINE,
        FeatureCategory.OPERATIONS,
        "Shuttle Route",
        subtype="shuttle_route",
        style_key="shuttle_route",
        menu_section="Event Routes",
    ),
    OperationalGeometryType(
        FeatureType.ROUTE,
        GeometryType.LINE,
        FeatureCategory.OPERATIONS,
        "Emergency Access Route",
        subtype="emergency_access_route",
        style_key="emergency_access_route",
        menu_section="Event Routes",
    ),
    OperationalGeometryType(
        FeatureType.ROUTE,
        GeometryType.LINE,
        FeatureCategory.OPERATIONS,
        "Detour Route",
        subtype="detour_route",
        style_key="detour_route",
        menu_section="Event Routes",
    ),
    OperationalGeometryType(
        FeatureType.ROUTE,
        GeometryType.LINE,
        FeatureCategory.OPERATIONS,
        "Evacuation Route",
        subtype="evacuation_route",
        style_key="evacuation_route",
        menu_section="Event Routes",
    ),
    OperationalGeometryType(
        FeatureType.ROUTE,
        GeometryType.LINE,
        FeatureCategory.OPERATIONS,
        "Staff / Service Vehicle Route",
        subtype="staff_service_route",
        style_key="staff_service_route",
        menu_section="Event Routes",
    ),
    OperationalGeometryType(
        FeatureType.CONTAINMENT_LINE,
        GeometryType.LINE,
        FeatureCategory.OPERATIONS,
        "Road Closure",
        subtype="road_closure",
        style_key="road_closure",
        menu_section="Closures & Barriers",
    ),
    OperationalGeometryType(
        FeatureType.CONTAINMENT_LINE,
        GeometryType.LINE,
        FeatureCategory.OPERATIONS,
        "Soft Closure",
        subtype="soft_closure",
        style_key="soft_closure",
        menu_section="Closures & Barriers",
    ),
    OperationalGeometryType(
        FeatureType.CONTAINMENT_LINE,
        GeometryType.LINE,
        FeatureCategory.OPERATIONS,
        "Barricade Line",
        subtype="barricade_line",
        style_key="barricade_line",
        menu_section="Closures & Barriers",
    ),
    OperationalGeometryType(
        FeatureType.CONTAINMENT_LINE,
        GeometryType.LINE,
        FeatureCategory.OPERATIONS,
        "Temporary Barrier / Fence",
        subtype="temporary_barrier",
        style_key="temporary_barrier",
        menu_section="Closures & Barriers",
    ),
    OperationalGeometryType(
        FeatureType.CONTAINMENT_LINE,
        GeometryType.LINE,
        FeatureCategory.OPERATIONS,
        "Queue Divider",
        subtype="queue_divider",
        style_key="queue_divider",
        menu_section="Control Lines",
    ),
    OperationalGeometryType(
        FeatureType.CONTAINMENT_LINE,
        GeometryType.LINE,
        FeatureCategory.OPERATIONS,
        "Course Edge / Keep Clear",
        subtype="course_edge",
        style_key="course_edge",
        menu_section="Control Lines",
    ),
    OperationalGeometryType(
        FeatureType.CONTAINMENT_LINE,
        GeometryType.LINE,
        FeatureCategory.OPERATIONS,
        "No-Cross Line",
        subtype="no_cross_line",
        style_key="no_cross_line",
        menu_section="Control Lines",
    ),
    OperationalGeometryType(
        FeatureType.CONTAINMENT_LINE,
        GeometryType.LINE,
        FeatureCategory.OPERATIONS,
        "Crossing Control Zone",
        subtype="crossing_control_zone",
        style_key="crossing_control_zone",
        menu_section="Control Lines",
    ),
)

OPERATIONAL_EVENT_AREA_TYPES: tuple[OperationalGeometryType, ...] = (
    OperationalGeometryType(
        FeatureType.OPERATIONAL_BOUNDARY,
        GeometryType.POLYGON,
        FeatureCategory.PLANNING,
        "Ceremony Area",
        subtype="ceremony_area",
        style_key="ceremony_area",
        menu_section="Public & Event Areas",
    ),
    OperationalGeometryType(
        FeatureType.OPERATIONAL_BOUNDARY,
        GeometryType.POLYGON,
        FeatureCategory.PLANNING,
        "Spectator Area",
        subtype="spectator_area",
        style_key="spectator_area",
        menu_section="Public & Event Areas",
    ),
    OperationalGeometryType(
        FeatureType.OPERATIONAL_BOUNDARY,
        GeometryType.POLYGON,
        FeatureCategory.PLANNING,
        "Vendor Area",
        subtype="vendor_area",
        style_key="vendor_area",
        menu_section="Public & Event Areas",
    ),
    OperationalGeometryType(
        FeatureType.OPERATIONAL_BOUNDARY,
        GeometryType.POLYGON,
        FeatureCategory.PLANNING,
        "Volunteer Area",
        subtype="volunteer_area",
        style_key="volunteer_area",
        menu_section="Support Areas",
    ),
    OperationalGeometryType(
        FeatureType.OPERATIONAL_BOUNDARY,
        GeometryType.POLYGON,
        FeatureCategory.PLANNING,
        "Staff Area",
        subtype="staff_area",
        style_key="staff_area",
        menu_section="Support Areas",
    ),
    OperationalGeometryType(
        FeatureType.STAGING_AREA,
        GeometryType.POLYGON,
        FeatureCategory.LOGISTICS,
        "Logistics Area",
        subtype="logistics_area",
        style_key="logistics_area",
        menu_section="Support Areas",
    ),
    OperationalGeometryType(
        FeatureType.STAGING_AREA,
        GeometryType.POLYGON,
        FeatureCategory.LOGISTICS,
        "Rehab Area",
        subtype="rehab_area",
        style_key="rehab_area",
        menu_section="Support Areas",
    ),
    OperationalGeometryType(
        FeatureType.BASE_CAMP,
        GeometryType.POLYGON,
        FeatureCategory.LOGISTICS,
        "Command Area",
        subtype="command_area",
        style_key="command_area",
        menu_section="Support Areas",
    ),
    OperationalGeometryType(
        FeatureType.STAGING_AREA,
        GeometryType.POLYGON,
        FeatureCategory.LOGISTICS,
        "General Parking",
        subtype="general_parking",
        style_key="general_parking",
        menu_section="Parking & Queue",
    ),
    OperationalGeometryType(
        FeatureType.STAGING_AREA,
        GeometryType.POLYGON,
        FeatureCategory.LOGISTICS,
        "Accessible Parking",
        subtype="accessible_parking",
        style_key="accessible_parking",
        menu_section="Parking & Queue",
    ),
    OperationalGeometryType(
        FeatureType.STAGING_AREA,
        GeometryType.POLYGON,
        FeatureCategory.LOGISTICS,
        "Overflow Parking",
        subtype="overflow_parking",
        style_key="overflow_parking",
        menu_section="Parking & Queue",
    ),
    OperationalGeometryType(
        FeatureType.STAGING_AREA,
        GeometryType.POLYGON,
        FeatureCategory.LOGISTICS,
        "Queue Area",
        subtype="queue_area",
        style_key="queue_area",
        menu_section="Parking & Queue",
    ),
    OperationalGeometryType(
        FeatureType.NO_ENTRY_ZONE,
        GeometryType.POLYGON,
        FeatureCategory.SAFETY,
        "Restricted Area",
        subtype="restricted_area",
        style_key="restricted_area",
        menu_section="Restricted & Safety",
    ),
    OperationalGeometryType(
        FeatureType.NO_ENTRY_ZONE,
        GeometryType.POLYGON,
        FeatureCategory.SAFETY,
        "Emergency Access / Keep Clear Zone",
        subtype="emergency_keep_clear",
        style_key="emergency_keep_clear",
        menu_section="Restricted & Safety",
    ),
    OperationalGeometryType(
        FeatureType.HAZARD_ZONE,
        GeometryType.POLYGON,
        FeatureCategory.SAFETY,
        "Hazard Area (Event)",
        subtype="hazard_area",
        style_key="hazard_area",
        menu_section="Restricted & Safety",
    ),
)

OPERATIONAL_GEOMETRY_TYPES: tuple[OperationalGeometryType, ...] = (
    OPERATIONAL_LINE_TYPES
    + OPERATIONAL_AREA_TYPES
    + OPERATIONAL_EVENT_LINE_TYPES
    + OPERATIONAL_EVENT_AREA_TYPES
)


def operational_geometry_type(
    feature_type: FeatureType | str,
    geometry_type: GeometryType,
    subtype: str | None = None,
) -> OperationalGeometryType:
    """Look up a catalog entry by feature type, geometry and optional subtype."""
    resolved = feature_type if isinstance(feature_type, FeatureType) else FeatureType(feature_type)
    for definition in OPERATIONAL_GEOMETRY_TYPES:
        if (
            definition.feature_type is resolved
            and definition.geometry_type is geometry_type
            and definition.subtype == subtype
        ):
            return definition
    raise KeyError(f"{resolved.value}:{geometry_type.value}:{subtype}")


def primary_line_types() -> tuple[OperationalGeometryType, ...]:
    return tuple(d for d in OPERATIONAL_LINE_TYPES if d.primary)


def primary_area_types() -> tuple[OperationalGeometryType, ...]:
    return tuple(d for d in OPERATIONAL_AREA_TYPES if d.primary)
