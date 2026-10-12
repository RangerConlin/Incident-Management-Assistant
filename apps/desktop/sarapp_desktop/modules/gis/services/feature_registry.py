from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

from modules.gis.models.feature_types import FeatureType
from modules.gis.models.geometry_types import GeometryType


@dataclass(frozen=True, slots=True)
class FeatureRegistration:
    feature_type: FeatureType
    owner_module: str
    allowed_geometry_types: tuple[GeometryType, ...]
    default_layer_key: str
    default_style_key: str
    allow_multiple_links: bool = True
    inspector_target: str | None = None


class FeatureRegistry:
    """Central rules table for all spatial feature types."""

    def __init__(self, registrations: Iterable[FeatureRegistration]) -> None:
        self._registrations = {item.feature_type: item for item in registrations}

    def get(self, feature_type: FeatureType) -> FeatureRegistration:
        return self._registrations[feature_type]

    def has_feature_type(self, feature_type: FeatureType) -> bool:
        return feature_type in self._registrations

    def list_feature_types(self) -> list[FeatureType]:
        return list(self._registrations.keys())

    def can_use_geometry(self, feature_type: FeatureType, geometry_type: GeometryType) -> bool:
        registration = self.get(feature_type)
        return geometry_type in registration.allowed_geometry_types


@lru_cache(maxsize=1)
def get_default_feature_registry() -> FeatureRegistry:
    line = (GeometryType.LINE,)
    point = (GeometryType.POINT,)
    polygon = (GeometryType.POLYGON,)
    point_or_line = (GeometryType.POINT, GeometryType.LINE)
    point_or_polygon = (GeometryType.POINT, GeometryType.POLYGON)

    return FeatureRegistry(
        [
            FeatureRegistration(FeatureType.TEAM_LOCATION, "operations", point, "teams", "team_default"),
            FeatureRegistration(FeatureType.TEAM_TRACK, "operations", line, "tracks", "team_track"),
            FeatureRegistration(FeatureType.TASK_POINT, "operations", point, "tasks", "task_default"),
            FeatureRegistration(FeatureType.TASK_ROUTE, "operations", line, "tasks", "task_route"),
            FeatureRegistration(FeatureType.TASK_AREA, "operations", polygon, "tasks", "task_area"),
            FeatureRegistration(FeatureType.ASSIGNMENT_AREA, "operations", polygon, "assignments", "assignment_area"),
            FeatureRegistration(FeatureType.ROUTE, "operations", line, "planning_overlays", "route"),
            FeatureRegistration(FeatureType.CONTAINMENT_LINE, "operations", line, "planning_overlays", "containment"),
            FeatureRegistration(FeatureType.SEARCH_SEGMENT, "operations", polygon, "planning_overlays", "segment"),
            FeatureRegistration(FeatureType.SEARCH_GRID, "planning", polygon, "planning_overlays", "grid"),
            FeatureRegistration(FeatureType.CLUE, "intel", point_or_polygon, "clues", "clue"),
            FeatureRegistration(FeatureType.SIGHTING, "intel", point_or_polygon, "clues", "sighting"),
            FeatureRegistration(FeatureType.SUBJECT_LKP, "intel", point, "subjects", "subject_lkp"),
            FeatureRegistration(FeatureType.SUBJECT_PLS, "intel", point, "subjects", "subject_pls"),
            FeatureRegistration(FeatureType.SUBJECT_EVENT_LOCATION, "intel", point, "subjects", "subject_event"),
            FeatureRegistration(FeatureType.SUBJECT_INTENDED_ROUTE, "intel", point_or_line, "subjects", "subject_route"),
            FeatureRegistration(FeatureType.INTERVIEW_LOCATION, "intel", point, "subjects", "interview"),
            FeatureRegistration(FeatureType.EVIDENCE_LOCATION, "intel", point, "subjects", "evidence"),
            FeatureRegistration(FeatureType.HAZARD_ZONE, "safety", point_or_polygon, "hazards", "hazard"),
            FeatureRegistration(FeatureType.NO_ENTRY_ZONE, "safety", polygon, "hazards", "no_entry"),
            FeatureRegistration(FeatureType.CLOSURE_AREA, "safety", polygon, "hazards", "closure"),
            FeatureRegistration(FeatureType.OPERATIONAL_BOUNDARY, "planning", polygon, "planning_overlays", "boundary"),
            FeatureRegistration(FeatureType.REPEATER_SITE, "communications", point, "comm_sites", "repeater"),
            FeatureRegistration(FeatureType.RADIO_DEAD_ZONE, "communications", polygon, "comm_sites", "radio_dead_zone"),
            FeatureRegistration(FeatureType.CHECK_IN_POINT, "communications", point, "comm_sites", "checkin"),
            FeatureRegistration(FeatureType.VEHICLE_LOCATION, "logistics", point, "logistics_sites", "vehicle"),
            FeatureRegistration(FeatureType.AIRCRAFT_TRACK, "logistics", line, "tracks", "aircraft_track"),
            FeatureRegistration(FeatureType.MED_UNIT_LOCATION, "medical", point, "logistics_sites", "med_unit"),
            FeatureRegistration(FeatureType.STAGING_AREA, "logistics", point_or_polygon, "logistics_sites", "staging"),
            FeatureRegistration(FeatureType.BASE_CAMP, "logistics", point_or_polygon, "logistics_sites", "base_camp"),
            FeatureRegistration(FeatureType.HELISPOT, "logistics", point, "logistics_sites", "helispot"),
            FeatureRegistration(FeatureType.LANDING_ZONE, "logistics", point_or_polygon, "logistics_sites", "landing_zone"),
            FeatureRegistration(FeatureType.ROADBLOCK, "operations", point, "assignments", "roadblock"),
            FeatureRegistration(FeatureType.PLANNING_SKETCH, "planning", point_or_line + polygon, "planning_overlays", "planning_sketch"),
            FeatureRegistration(
                FeatureType.IMPORTED_OVERLAY_REFERENCE,
                "planning",
                point_or_line + polygon,
                "imported_overlays",
                "imported_overlay",
                inspector_target="gis.imported_overlay",
            ),
        ]
    )
