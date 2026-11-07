"""Immutable ICS reference definitions used by incident activity logs.

These definitions are application doctrine, not an editable catalog and not
incident organization records. An incident may create similarly named custom
positions or organizational elements without changing these identities.
"""
from __future__ import annotations

from typing import Final


# Named organizational elements that are present in the standard ICS structure.
# Repeatable elements (a particular branch, division, group, strike team, task
# force, or single resource) are incident-created instances instead.
NAMED_ORGANIZATIONAL_ELEMENTS: Final[tuple[tuple[str, str, str], ...]] = (
    ("command", "Command", "Incident Commander"),
    ("operations_section", "Operations Section", "Operations Section Chief"),
    ("planning_section", "Planning Section", "Planning Section Chief"),
    ("logistics_section", "Logistics Section", "Logistics Section Chief"),
    ("finance_admin_section", "Finance / Administration Section", "Finance / Administration Section Chief"),
    ("intelligence_investigations", "Intelligence / Investigations", "Intelligence / Investigations Section Chief"),
    ("air_operations_branch", "Air Operations Branch", "Air Operations Branch Director"),
    ("resources_unit", "Resources Unit", "Resources Unit Leader"),
    ("situation_unit", "Situation Unit", "Situation Unit Leader"),
    ("documentation_unit", "Documentation Unit", "Documentation Unit Leader"),
    ("demobilization_unit", "Demobilization Unit", "Demobilization Unit Leader"),
    ("service_branch", "Service Branch", "Service Branch Director"),
    ("communications_unit", "Communications Unit", "Communications Unit Leader"),
    ("medical_unit", "Medical Unit", "Medical Unit Leader"),
    ("food_unit", "Food Unit", "Food Unit Leader"),
    ("support_branch", "Support Branch", "Support Branch Director"),
    ("supply_unit", "Supply Unit", "Supply Unit Leader"),
    ("facilities_unit", "Facilities Unit", "Facilities Unit Leader"),
    ("ground_support_unit", "Ground Support Unit", "Ground Support Unit Leader"),
    ("time_unit", "Time Unit", "Time Unit Leader"),
    ("procurement_unit", "Procurement Unit", "Procurement Unit Leader"),
    ("compensation_claims_unit", "Compensation / Claims Unit", "Compensation / Claims Unit Leader"),
    ("cost_unit", "Cost Unit", "Cost Unit Leader"),
)


# Standard named positions. Each is an always-available reference log whether
# or not the incident organization has assigned a person to the position.
REFERENCE_POSITIONS: Final[tuple[tuple[str, str], ...]] = (
    ("incident_commander", "Incident Commander"),
    ("public_information_officer", "Public Information Officer"),
    ("safety_officer", "Safety Officer"),
    ("liaison_officer", "Liaison Officer"),
    ("operations_section_chief", "Operations Section Chief"),
    ("planning_section_chief", "Planning Section Chief"),
    ("logistics_section_chief", "Logistics Section Chief"),
    ("finance_admin_section_chief", "Finance / Administration Section Chief"),
    ("intelligence_investigations_section_chief", "Intelligence / Investigations Section Chief"),
    ("branch_director", "Branch Director"),
    ("division_group_supervisor", "Division / Group Supervisor"),
    ("strike_team_task_force_leader", "Strike Team / Task Force Leader"),
    ("single_resource_boss", "Single Resource Boss"),
    ("staging_area_manager", "Staging Area Manager"),
    ("air_operations_branch_director", "Air Operations Branch Director"),
    ("air_tactical_group_supervisor", "Air Tactical Group Supervisor"),
    ("air_support_group_supervisor", "Air Support Group Supervisor"),
    ("helibase_manager", "Helibase Manager"),
    ("helispot_manager", "Helispot Manager"),
    ("resources_unit_leader", "Resources Unit Leader"),
    ("check_in_status_recorder", "Check-In / Status Recorder"),
    ("situation_unit_leader", "Situation Unit Leader"),
    ("display_processor", "Display Processor"),
    ("field_observer", "Field Observer"),
    ("weather_observer", "Weather Observer"),
    ("documentation_unit_leader", "Documentation Unit Leader"),
    ("demobilization_unit_leader", "Demobilization Unit Leader"),
    ("technical_specialist", "Technical Specialist"),
    ("service_branch_director", "Service Branch Director"),
    ("communications_unit_leader", "Communications Unit Leader"),
    ("medical_unit_leader", "Medical Unit Leader"),
    ("food_unit_leader", "Food Unit Leader"),
    ("support_branch_director", "Support Branch Director"),
    ("supply_unit_leader", "Supply Unit Leader"),
    ("ordering_manager", "Ordering Manager"),
    ("receiving_distribution_manager", "Receiving and Distribution Manager"),
    ("facilities_unit_leader", "Facilities Unit Leader"),
    ("security_manager", "Security Manager"),
    ("base_manager", "Base Manager"),
    ("camp_manager", "Camp Manager"),
    ("ground_support_unit_leader", "Ground Support Unit Leader"),
    ("equipment_manager", "Equipment Manager"),
    ("time_unit_leader", "Time Unit Leader"),
    ("personnel_time_recorder", "Personnel Time Recorder"),
    ("equipment_time_recorder", "Equipment Time Recorder"),
    ("procurement_unit_leader", "Procurement Unit Leader"),
    ("compensation_claims_unit_leader", "Compensation / Claims Unit Leader"),
    ("compensation_for_injury_specialist", "Compensation for Injury Specialist"),
    ("claims_specialist", "Claims Specialist"),
    ("cost_unit_leader", "Cost Unit Leader"),
)


# Authoritative repeatable types; incidents own their named instances.
ORGANIZATIONAL_ELEMENT_TYPES: Final[tuple[tuple[str, str], ...]] = (
    ("section", "Section"),
    ("branch", "Branch"),
    ("division", "Division"),
    ("group", "Group"),
    ("unit", "Unit"),
    ("strike_team", "Strike Team"),
    ("task_force", "Task Force"),
    ("single_resource", "Single Resource"),
)


BUILTIN_LOGS: Final[tuple[dict[str, str], ...]] = tuple(
    {
        "key": key,
        "name": name,
        "prepared_by_position": prepared_by,
        "reference_kind": "organizational_element",
    }
    for key, name, prepared_by in NAMED_ORGANIZATIONAL_ELEMENTS
) + tuple(
    {
        "key": f"position:{key}",
        "name": name,
        "prepared_by_position": name,
        "reference_kind": "position",
    }
    for key, name in REFERENCE_POSITIONS
)

BUILTIN_LOG_BY_KEY: Final = {definition["key"]: definition for definition in BUILTIN_LOGS}
BUILTIN_LOG_KEYS: Final = frozenset(BUILTIN_LOG_BY_KEY)


def builtin_log_definitions() -> list[dict[str, object]]:
    """Return API-shaped, immutable saved-log definitions."""
    return [
        {
            "id": f"builtin:{definition['key']}",
            "key": definition["key"],
            "name": definition["name"],
            "unit_name": definition["name"],
            "prepared_by_position": definition["prepared_by_position"],
            "reference_kind": definition["reference_kind"],
            "filters": {"log_keys": [definition["key"]]},
            "builtin": True,
        }
        for definition in BUILTIN_LOGS
    ]
