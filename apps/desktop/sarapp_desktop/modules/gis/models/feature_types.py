from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FeatureCategory(str, Enum):
    OPERATIONS = "operations"
    INTEL = "intel"
    SAFETY = "safety"
    COMMUNICATIONS = "communications"
    LOGISTICS = "logistics"
    PLANNING = "planning"


class FeatureType(str, Enum):
    # Operations
    TEAM_LOCATION = "team_location"
    TEAM_TRACK = "team_track"
    TASK_POINT = "task_point"
    TASK_ROUTE = "task_route"
    TASK_AREA = "task_area"
    ASSIGNMENT_AREA = "assignment_area"
    ROUTE = "route"
    CONTAINMENT_LINE = "containment_line"
    SEARCH_SEGMENT = "search_segment"
    SEARCH_GRID = "search_grid"

    # Intel
    CLUE = "clue"
    SIGHTING = "sighting"
    SUBJECT_LKP = "subject_lkp"
    SUBJECT_PLS = "subject_pls"
    SUBJECT_EVENT_LOCATION = "subject_event_location"
    SUBJECT_INTENDED_ROUTE = "subject_intended_route"
    INTERVIEW_LOCATION = "interview_location"
    EVIDENCE_LOCATION = "evidence_location"

    # Safety
    HAZARD_ZONE = "hazard_zone"
    NO_ENTRY_ZONE = "no_entry_zone"
    CLOSURE_AREA = "closure_area"
    OPERATIONAL_BOUNDARY = "operational_boundary"

    # Communications
    REPEATER_SITE = "repeater_site"
    RADIO_DEAD_ZONE = "radio_dead_zone"
    CHECK_IN_POINT = "check_in_point"

    # Logistics
    VEHICLE_LOCATION = "vehicle_location"
    AIRCRAFT_TRACK = "aircraft_track"
    MED_UNIT_LOCATION = "med_unit_location"
    STAGING_AREA = "staging_area"
    BASE_CAMP = "base_camp"
    HELISPOT = "helispot"
    LANDING_ZONE = "landing_zone"
    ROADBLOCK = "roadblock"

    # Planning
    PLANNING_SKETCH = "planning_sketch"
    IMPORTED_OVERLAY_REFERENCE = "imported_overlay_reference"


@dataclass(frozen=True)
class FeatureTypeDefinition:
    feature_type: FeatureType
    category: FeatureCategory
    display_name: str
    description: str = ""
