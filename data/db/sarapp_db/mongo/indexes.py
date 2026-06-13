"""
MongoDB index definitions for SARApp.

Index creation is idempotent — PyMongo skips creation if an identical index
already exists. Calling these functions on every server startup is safe.
"""

from __future__ import annotations

import logging

from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.errors import OperationFailure

from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections

logger = logging.getLogger(__name__)


def _ensure_index(collection, keys, **kwargs) -> None:
    """Create an index, logging a warning on conflict instead of raising."""
    try:
        collection.create_index(keys, **kwargs)
    except OperationFailure as exc:
        logger.warning("Index conflict on '%s': %s", collection.name, exc)


# ---------------------------------------------------------------------------
# Incident database indexes
# ---------------------------------------------------------------------------

def create_incident_indexes(incident_db: Database) -> None:
    """Create required indexes for a per-incident database."""
    _create_teams_indexes(incident_db)
    _create_tasks_indexes(incident_db)
    _create_strategies_indexes(incident_db)
    _create_check_in_out_indexes(incident_db)
    _create_hazards_indexes(incident_db)
    _create_audit_logs_indexes(incident_db)
    _create_incident_organization_indexes(incident_db)
    _create_unit_logs_indexes(incident_db)
    _create_meetings_indexes(incident_db)
    _create_incident_channels_indexes(incident_db)
    _create_resources_indexes(incident_db)
    logger.debug("Incident database indexes verified: %s", incident_db.name)


def _create_teams_indexes(incident_db: Database) -> None:
    teams = incident_db[IncidentCollections.TEAMS]
    _ensure_index(teams, [("team_id", ASCENDING)], unique=True)
    _ensure_index(teams, [("name", ASCENDING)])
    _ensure_index(teams, [("status", ASCENDING)])


def _create_tasks_indexes(incident_db: Database) -> None:
    tasks = incident_db[IncidentCollections.TASKS]
    _ensure_index(tasks, [("incident_id", ASCENDING)])
    _ensure_index(tasks, [("status", ASCENDING)])
    _ensure_index(tasks, [("priority", ASCENDING)])
    _ensure_index(tasks, [("operational_period_id", ASCENDING)])
    # task_number unique within an incident
    _ensure_index(
        tasks,
        [("incident_id", ASCENDING), ("task_number", ASCENDING)],
        unique=True,
        name="task_number_unique_per_incident",
    )
    _ensure_index(tasks, [("linked_objective_ids", ASCENDING)])
    # Embedded assignment arrays — indexed for lookup by assigned resource
    _ensure_index(tasks, [("assigned_teams.team_id", ASCENDING)])
    _ensure_index(tasks, [("assigned_personnel.personnel_id", ASCENDING)])
    _ensure_index(tasks, [("assigned_vehicles.vehicle_id", ASCENDING)])
    _ensure_index(tasks, [("updated_at", DESCENDING)])
    _ensure_index(tasks, [("deleted", ASCENDING)])
    # Narrative entries embedded as array — indexed for critical flag lookups
    _ensure_index(tasks, [("narrative.critical", ASCENDING)])


def _create_strategies_indexes(incident_db: Database) -> None:
    strategies = incident_db[IncidentCollections.STRATEGIES]
    _ensure_index(strategies, [("incident_id", ASCENDING)])
    _ensure_index(strategies, [("operational_period_id", ASCENDING)])
    _ensure_index(strategies, [("status", ASCENDING)])
    _ensure_index(strategies, [("deleted", ASCENDING)])


def _create_check_in_out_indexes(incident_db: Database) -> None:
    check_in_out = incident_db[IncidentCollections.CHECK_IN_OUT]
    _ensure_index(check_in_out, [("incident_id", ASCENDING)])
    # resource_type distinguishes personnel / vehicle / aircraft / equipment
    _ensure_index(check_in_out, [("resource_type", ASCENDING)])
    _ensure_index(check_in_out, [("resource_id", ASCENDING)])
    _ensure_index(check_in_out, [("status", ASCENDING)])  # checked_in | checked_out
    _ensure_index(check_in_out, [("checked_in_at", DESCENDING)])
    _ensure_index(check_in_out, [("checked_out_at", DESCENDING)])
    _ensure_index(check_in_out, [("operational_period_id", ASCENDING)])


def _create_hazards_indexes(incident_db: Database) -> None:
    hazards = incident_db[IncidentCollections.HAZARDS]
    _ensure_index(hazards, [("incident_id", ASCENDING)])
    _ensure_index(hazards, [("hazard_type", ASCENDING)])
    _ensure_index(hazards, [("severity", ASCENDING)])
    _ensure_index(hazards, [("status", ASCENDING)])  # active | mitigated | resolved
    _ensure_index(hazards, [("deleted", ASCENDING)])


def _create_incident_channels_indexes(incident_db: Database) -> None:
    channels = incident_db[IncidentCollections.INCIDENT_CHANNELS]
    _ensure_index(channels, [("incident_id", ASCENDING)])
    _ensure_index(channels, [("channel_id", ASCENDING)], unique=True)
    _ensure_index(channels, [("master_id", ASCENDING)])
    _ensure_index(channels, [("function", ASCENDING)])
    _ensure_index(channels, [("include_on_205", ASCENDING)])


def _create_resources_indexes(incident_db: Database) -> None:
    resources = incident_db[IncidentCollections.RESOURCES]
    _ensure_index(resources, [("incident_id", ASCENDING)])
    _ensure_index(resources, [("resource_id", ASCENDING)], unique=True)
    _ensure_index(resources, [("resource_type", ASCENDING)])
    _ensure_index(resources, [("status", ASCENDING)])
    _ensure_index(resources, [("team_id", ASCENDING)])


def _create_incident_organization_indexes(incident_db: Database) -> None:
    org = incident_db[IncidentCollections.INCIDENT_ORGANIZATION]
    _ensure_index(org, [("incident_id", ASCENDING)])
    _ensure_index(org, [("version_id", ASCENDING)], unique=True)
    _ensure_index(org, [("op_period_id", ASCENDING)])
    _ensure_index(org, [("assignments.person_id", ASCENDING)])
    _ensure_index(org, [("assignments.position_id", ASCENDING)])


def _create_unit_logs_indexes(incident_db: Database) -> None:
    logs = incident_db[IncidentCollections.UNIT_LOGS]
    _ensure_index(logs, [("incident_id", ASCENDING)])
    _ensure_index(logs, [("stream_id", ASCENDING)], unique=True)
    _ensure_index(logs, [("kind", ASCENDING)])
    _ensure_index(logs, [("section", ASCENDING)])
    _ensure_index(logs, [("entries.critical_flag", ASCENDING)])
    _ensure_index(logs, [("entries.timestamp_utc", DESCENDING)])


def _create_meetings_indexes(incident_db: Database) -> None:
    meetings = incident_db[IncidentCollections.MEETINGS]
    _ensure_index(meetings, [("incident_id", ASCENDING)])
    _ensure_index(meetings, [("meeting_id", ASCENDING)], unique=True)
    _ensure_index(meetings, [("op_period_id", ASCENDING)])
    _ensure_index(meetings, [("meeting_date", ASCENDING)])
    _ensure_index(meetings, [("status", ASCENDING)])


def _create_audit_logs_indexes(incident_db: Database) -> None:
    audit = incident_db[IncidentCollections.AUDIT_LOGS]
    _ensure_index(audit, [("incident_id", ASCENDING)])
    _ensure_index(audit, [("entity_type", ASCENDING)])
    _ensure_index(audit, [("entity_id", ASCENDING)])
    _ensure_index(audit, [("timestamp", DESCENDING)])
    _ensure_index(audit, [("changed_by", ASCENDING)])


# ---------------------------------------------------------------------------
# Master database indexes
# ---------------------------------------------------------------------------

def create_master_indexes(master_db: Database) -> None:
    """Create required indexes for the sarapp_master database."""
    _create_personnel_indexes(master_db)
    _create_radio_channels_indexes(master_db)
    _create_hospitals_indexes(master_db)
    _create_hazard_types_indexes(master_db)
    _create_vehicles_indexes(master_db)
    _create_aircraft_indexes(master_db)
    _create_equipment_indexes(master_db)
    logger.debug("Master database indexes verified: %s", master_db.name)


def _create_personnel_indexes(master_db: Database) -> None:
    personnel = master_db[MasterCollections.PERSONNEL]
    _ensure_index(personnel, [("personnel_id", ASCENDING)], unique=True)
    _ensure_index(personnel, [("last_name", ASCENDING)])
    _ensure_index(personnel, [("organization", ASCENDING)])
    _ensure_index(personnel, [("status", ASCENDING)])
    # Certifications embedded — indexed for lookup by cert type
    _ensure_index(personnel, [("certifications.certification_type_id", ASCENDING)])


def _create_radio_channels_indexes(master_db: Database) -> None:
    channels = master_db[MasterCollections.RADIO_CHANNELS]
    _ensure_index(channels, [("channel_name", ASCENDING)], unique=True)
    _ensure_index(channels, [("zone", ASCENDING)])
    _ensure_index(channels, [("channel_number", ASCENDING)])
    _ensure_index(channels, [("resource_type", ASCENDING)])  # radio | repeater | tac | etc.


def _create_hospitals_indexes(master_db: Database) -> None:
    hospitals = master_db[MasterCollections.HOSPITALS]
    _ensure_index(hospitals, [("name", ASCENDING)])
    _ensure_index(hospitals, [("state", ASCENDING)])
    _ensure_index(hospitals, [("county", ASCENDING)])
    _ensure_index(hospitals, [("trauma_level", ASCENDING)])


def _create_hazard_types_indexes(master_db: Database) -> None:
    hazard_types = master_db[MasterCollections.HAZARD_TYPES]
    _ensure_index(hazard_types, [("name", ASCENDING)], unique=True)
    _ensure_index(hazard_types, [("category", ASCENDING)])


def _create_vehicles_indexes(master_db: Database) -> None:
    vehicles = master_db[MasterCollections.VEHICLES]
    _ensure_index(vehicles, [("vehicle_id", ASCENDING)], unique=True)
    _ensure_index(vehicles, [("agency", ASCENDING)])
    _ensure_index(vehicles, [("status", ASCENDING)])
    _ensure_index(vehicles, [("vehicle_type", ASCENDING)])


def _create_aircraft_indexes(master_db: Database) -> None:
    aircraft = master_db[MasterCollections.AIRCRAFT]
    _ensure_index(aircraft, [("aircraft_id", ASCENDING)], unique=True)
    _ensure_index(aircraft, [("agency", ASCENDING)])
    _ensure_index(aircraft, [("status", ASCENDING)])
    _ensure_index(aircraft, [("aircraft_type", ASCENDING)])


def _create_equipment_indexes(master_db: Database) -> None:
    equipment = master_db[MasterCollections.EQUIPMENT]
    _ensure_index(equipment, [("equipment_id", ASCENDING)], unique=True)
    _ensure_index(equipment, [("agency", ASCENDING)])
    _ensure_index(equipment, [("status", ASCENDING)])
    _ensure_index(equipment, [("equipment_type", ASCENDING)])
