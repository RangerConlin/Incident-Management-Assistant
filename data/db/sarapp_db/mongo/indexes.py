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


def _drop_index_if_exists(collection, index_name: str) -> None:
    """Drop a named index if it exists; no-op otherwise."""
    try:
        existing = {info["name"] for info in collection.index_information().values()}
        if index_name in existing:
            collection.drop_index(index_name)
            logger.info("Dropped stale index '%s' from '%s'", index_name, collection.name)
    except OperationFailure as exc:
        logger.warning("Could not drop index '%s' from '%s': %s", index_name, collection.name, exc)


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
    _create_medical_indexes(incident_db)
    _create_safety_indexes(incident_db)
    _create_public_information_indexes(incident_db)
    _create_resources_indexes(incident_db)
    _create_intel_indexes(incident_db)
    _create_approval_indexes(incident_db)
    _create_weather_indexes(incident_db)
    _create_facilities_indexes(incident_db)
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
    _ensure_index(tasks, [("assigned_personnel.person_record", ASCENDING)])
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


def _create_medical_indexes(incident_db: Database) -> None:
    for name in (
        IncidentCollections.ICS_206_AID_STATIONS,
        IncidentCollections.ICS_206_AMBULANCE_SERVICES,
        IncidentCollections.ICS_206_HOSPITALS,
        IncidentCollections.ICS_206_AIR_AMBULANCE,
        IncidentCollections.ICS_206_MEDICAL_COMMS,
    ):
        col = incident_db[name]
        _ensure_index(col, [("incident_id", ASCENDING)])
        _ensure_index(col, [("op_period", ASCENDING)])
        _ensure_index(col, [("id", ASCENDING)], unique=True)
        _ensure_index(col, [("deleted", ASCENDING)])

    procedures = incident_db[IncidentCollections.ICS_206_PROCEDURES]
    _ensure_index(procedures, [("incident_id", ASCENDING)])
    _ensure_index(
        procedures,
        [("incident_id", ASCENDING), ("op_period", ASCENDING)],
        unique=True,
        name="ics206_procedures_unique_per_op",
    )

    signatures = incident_db[IncidentCollections.ICS_206_SIGNATURES]
    _ensure_index(signatures, [("incident_id", ASCENDING)])
    _ensure_index(
        signatures,
        [("incident_id", ASCENDING), ("op_period", ASCENDING)],
        unique=True,
        name="ics206_signatures_unique_per_op",
    )


def _create_safety_indexes(incident_db: Database) -> None:
    for name in (
        IncidentCollections.SAFETY_REPORTS,
        IncidentCollections.MEDICAL_INCIDENTS,
        IncidentCollections.TRIAGE_ENTRIES,
        IncidentCollections.HAZARD_ZONES,
        IncidentCollections.CAP_ORM_SUMMARIES,
        IncidentCollections.CAP_ORM_FORMS,
        IncidentCollections.CAP_ORM_HAZARDS,
        IncidentCollections.ICS_206_BUILDS,
    ):
        col = incident_db[name]
        _ensure_index(col, [("incident_id", ASCENDING)])
        _ensure_index(col, [("id", ASCENDING)], unique=True)
        _ensure_index(col, [("deleted", ASCENDING)])

    reports = incident_db[IncidentCollections.SAFETY_REPORTS]
    _ensure_index(reports, [("severity", ASCENDING)])
    _ensure_index(reports, [("flagged", ASCENDING)])
    _ensure_index(reports, [("time", DESCENDING)])

    forms = incident_db[IncidentCollections.CAP_ORM_FORMS]
    _ensure_index(
        forms,
        [("incident_id", ASCENDING), ("op_period", ASCENDING)],
        unique=True,
        name="cap_orm_form_unique_per_op",
    )
    _ensure_index(forms, [("status", ASCENDING)])
    _ensure_index(forms, [("highest_residual_risk", ASCENDING)])

    hazards = incident_db[IncidentCollections.CAP_ORM_HAZARDS]
    _ensure_index(hazards, [("form_id", ASCENDING)])
    _ensure_index(hazards, [("residual_risk", ASCENDING)])

    audit = incident_db[IncidentCollections.CAP_ORM_AUDIT]
    _ensure_index(audit, [("incident_id", ASCENDING)])
    _ensure_index(audit, [("entity", ASCENDING), ("entity_id", ASCENDING)])
    _ensure_index(audit, [("ts_iso", DESCENDING)])


def _create_public_information_indexes(incident_db: Database) -> None:
    messages = incident_db[IncidentCollections.PIO_MESSAGES]
    _ensure_index(messages, [("incident_id", ASCENDING)])
    _ensure_index(messages, [("id", ASCENDING)], unique=True)
    _ensure_index(messages, [("status", ASCENDING)])
    _ensure_index(messages, [("type", ASCENDING)])
    _ensure_index(messages, [("audience", ASCENDING)])
    _ensure_index(messages, [("updated_at", DESCENDING)])

    revisions = incident_db[IncidentCollections.PIO_MESSAGE_REVISIONS]
    _ensure_index(revisions, [("message_id", ASCENDING)])
    _ensure_index(revisions, [("created_at", DESCENDING)])

    approvals = incident_db[IncidentCollections.PIO_APPROVALS]
    _ensure_index(approvals, [("message_id", ASCENDING)])
    _ensure_index(approvals, [("timestamp", ASCENDING)])

    media = incident_db[IncidentCollections.PIO_MEDIA_LOG]
    _ensure_index(media, [("id", ASCENDING)], unique=True)
    _ensure_index(media, [("status", ASCENDING)])
    _ensure_index(media, [("time", DESCENDING)])

    misinformation = incident_db[IncidentCollections.PIO_MISINFORMATION_ITEMS]
    _ensure_index(misinformation, [("id", ASCENDING)], unique=True)
    _ensure_index(misinformation, [("status", ASCENDING)])
    _ensure_index(misinformation, [("last_update", DESCENDING)])

    timeline = incident_db[IncidentCollections.PIO_MISINFORMATION_TIMELINE]
    _ensure_index(timeline, [("item_id", ASCENDING)])
    _ensure_index(timeline, [("event_time", ASCENDING)])

    talking_points = incident_db[IncidentCollections.PIO_TALKING_POINTS]
    _ensure_index(talking_points, [("id", ASCENDING)], unique=True)
    _ensure_index(talking_points, [("status", ASCENDING)])
    _ensure_index(talking_points, [("updated_at", DESCENDING)])

    templates = incident_db[IncidentCollections.PIO_TEMPLATES]
    _ensure_index(templates, [("id", ASCENDING)], unique=True)
    _ensure_index(templates, [("is_active", ASCENDING)])
    _ensure_index(templates, [("template_name", ASCENDING)])

    distribution = incident_db[IncidentCollections.PIO_DISTRIBUTION_LOG]
    _ensure_index(distribution, [("id", ASCENDING)], unique=True)
    _ensure_index(distribution, [("message_id", ASCENDING)])
    _ensure_index(distribution, [("distributed_at", DESCENDING)])


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
    _ensure_index(org, [("assignments.person_record", ASCENDING)])
    _ensure_index(org, [("assignments.position_id", ASCENDING)])

    positions = incident_db[IncidentCollections.ORG_POSITIONS]
    _ensure_index(positions, [("incident_id", ASCENDING)])
    _ensure_index(positions, [("position_id", ASCENDING)], unique=True)
    _ensure_index(positions, [("status", ASCENDING)])

    assignments = incident_db[IncidentCollections.ORG_ASSIGNMENTS]
    _ensure_index(assignments, [("incident_id", ASCENDING)])
    _ensure_index(assignments, [("assignment_id", ASCENDING)], unique=True)
    _ensure_index(assignments, [("position_id", ASCENDING)])
    _ensure_index(assignments, [("person_record", ASCENDING)])
    _ensure_index(assignments, [("end_time", ASCENDING)])


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


def _create_intel_indexes(incident_db: Database) -> None:
    """Indexes for the Module 7 All-Hazards Intel collections."""
    subjects = incident_db[IncidentCollections.INTEL_SUBJECTS]
    _ensure_index(subjects, [("incident_id", ASCENDING)])
    _ensure_index(subjects, [("subject_type", ASCENDING)])
    _ensure_index(subjects, [("status", ASCENDING)])
    _ensure_index(subjects, [("deleted", ASCENDING)])
    _ensure_index(subjects, [("updated_at", DESCENDING)])

    leads = incident_db[IncidentCollections.INTEL_LEADS]
    _ensure_index(leads, [("incident_id", ASCENDING)])
    _ensure_index(leads, [("status", ASCENDING)])
    _ensure_index(leads, [("priority", ASCENDING)])
    _ensure_index(leads, [("assigned_to", ASCENDING)])
    _ensure_index(leads, [("deleted", ASCENDING)])
    _ensure_index(leads, [("updated_at", DESCENDING)])
    # lead_number unique within an incident
    _ensure_index(
        leads,
        [("incident_id", ASCENDING), ("lead_number", ASCENDING)],
        unique=True,
        sparse=True,
        name="lead_number_unique_per_incident",
    )

    items = incident_db[IncidentCollections.INTEL_ITEMS]
    _ensure_index(items, [("incident_id", ASCENDING)])
    _ensure_index(items, [("item_type", ASCENDING)])
    _ensure_index(items, [("status", ASCENDING)])
    _ensure_index(items, [("priority", ASCENDING)])
    _ensure_index(items, [("trend", ASCENDING)])
    _ensure_index(items, [("deleted", ASCENDING)])
    _ensure_index(items, [("updated_at", DESCENDING)])
    # Embedded observations array — indexed for time-range queries
    _ensure_index(items, [("observations.observed_at", DESCENDING)])
    _ensure_index(items, [("linked_subject_ids", ASCENDING)])
    _ensure_index(items, [("linked_task_ids", ASCENDING)])

    assessments = incident_db[IncidentCollections.INTEL_ASSESSMENTS]
    _ensure_index(assessments, [("incident_id", ASCENDING)])
    _ensure_index(assessments, [("status", ASCENDING)])
    _ensure_index(assessments, [("confidence", ASCENDING)])
    _ensure_index(assessments, [("deleted", ASCENDING)])
    _ensure_index(assessments, [("updated_at", DESCENDING)])
    _ensure_index(assessments, [("linked_item_ids", ASCENDING)])

    log = incident_db[IncidentCollections.INTEL_LOG]
    _ensure_index(log, [("incident_id", ASCENDING)])
    _ensure_index(log, [("entity_type", ASCENDING)])
    _ensure_index(log, [("entity_id", ASCENDING)])
    _ensure_index(log, [("event_type", ASCENDING)])
    _ensure_index(log, [("logged_at", DESCENDING)])

    reports = incident_db[IncidentCollections.INTEL_REPORTS]
    _ensure_index(reports, [("incident_id", ASCENDING)])
    _ensure_index(reports, [("report_type", ASCENDING)])
    _ensure_index(reports, [("status", ASCENDING)])
    _ensure_index(reports, [("deleted", ASCENDING)])
    _ensure_index(reports, [("created_at", DESCENDING)])


def _create_weather_indexes(incident_db: Database) -> None:
    weather = incident_db[IncidentCollections.WEATHER_DATA]
    _ensure_index(weather, [("incident_id", ASCENDING)])
    _ensure_index(weather, [("key", ASCENDING)])


def _create_facilities_indexes(incident_db: Database) -> None:
    facilities = incident_db[IncidentCollections.FACILITIES]
    _ensure_index(facilities, [("incident_id", ASCENDING)])
    _ensure_index(facilities, [("facility_type", ASCENDING)])
    _ensure_index(facilities, [("status", ASCENDING)])
    _ensure_index(facilities, [("is_primary", ASCENDING)])
    _ensure_index(facilities, [("name", ASCENDING)])
    _ensure_index(facilities, [("latitude", ASCENDING), ("longitude", ASCENDING)])
    _ensure_index(facilities, [("deleted", ASCENDING)])


def _create_approval_indexes(incident_db: Database) -> None:
    instances = incident_db[IncidentCollections.APPROVAL_INSTANCES]
    _ensure_index(instances, [("incident_id", ASCENDING)])
    _ensure_index(
        instances,
        [("incident_id", ASCENDING), ("entity_type", ASCENDING), ("entity_id", ASCENDING)],
        unique=True,
        name="approval_instance_unique_per_entity",
    )
    _ensure_index(instances, [("status", ASCENDING)])
    _ensure_index(instances, [("steps.status", ASCENDING)])
    _ensure_index(instances, [("steps.resolved_actor_id", ASCENDING)])

    records = incident_db[IncidentCollections.APPROVAL_RECORDS]
    _ensure_index(records, [("incident_id", ASCENDING)])
    _ensure_index(records, [("entity_type", ASCENDING), ("entity_id", ASCENDING)])
    _ensure_index(records, [("actor_id", ASCENDING)])
    _ensure_index(records, [("timestamp", DESCENDING)])


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
    _create_ems_agencies_indexes(master_db)
    _create_hazard_types_indexes(master_db)
    _create_vehicles_indexes(master_db)
    _create_aircraft_indexes(master_db)
    _create_equipment_indexes(master_db)
    _create_user_presence_indexes(master_db)
    logger.debug("Master database indexes verified: %s", master_db.name)


def _create_personnel_indexes(master_db: Database) -> None:
    personnel = master_db[MasterCollections.PERSONNEL]
    # Drop stale unique index from old schema that used personnel_id instead of person_id
    _drop_index_if_exists(personnel, "personnel_id_1")
    _ensure_index(personnel, [("person_record", ASCENDING)], unique=True)
    _ensure_index(personnel, [("last_name", ASCENDING)])
    _ensure_index(personnel, [("organization", ASCENDING)])
    _ensure_index(personnel, [("status", ASCENDING)])
    # Certifications embedded — indexed for lookup by cert type
    _ensure_index(personnel, [("certifications.certification_type_id", ASCENDING)])


def _create_user_presence_indexes(master_db: Database) -> None:
    users = master_db[MasterCollections.USERS]
    _ensure_index(users, [("user_id", ASCENDING)], unique=True)
    _ensure_index(users, [("username", ASCENDING)], unique=True)
    _ensure_index(users, [("person_record", ASCENDING)])

    sessions = master_db[MasterCollections.USER_SESSIONS]
    _ensure_index(sessions, [("session_id", ASCENDING)], unique=True)
    _ensure_index(sessions, [("ended_at", ASCENDING), ("status", ASCENDING), ("last_seen_at", DESCENDING)])
    _ensure_index(sessions, [("incident_id", ASCENDING), ("ended_at", ASCENDING), ("last_seen_at", DESCENDING)])
    _ensure_index(sessions, [("person_record", ASCENDING)])


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


def _create_ems_agencies_indexes(master_db: Database) -> None:
    agencies = master_db[MasterCollections.EMS_AGENCIES]
    _ensure_index(agencies, [("id", ASCENDING)], unique=True)
    _ensure_index(agencies, [("name", ASCENDING)])
    _ensure_index(agencies, [("type", ASCENDING)])
    _ensure_index(agencies, [("phone", ASCENDING)])
    _ensure_index(agencies, [("is_active", ASCENDING)])


def _create_hazard_types_indexes(master_db: Database) -> None:
    hazard_types = master_db[MasterCollections.HAZARD_TYPES]
    _ensure_index(hazard_types, [("name", ASCENDING)], unique=True)
    _ensure_index(hazard_types, [("category", ASCENDING)])


def _create_vehicles_indexes(master_db: Database) -> None:
    vehicles = master_db[MasterCollections.VEHICLES]
    _ensure_index(vehicles, [("vehicle_record", ASCENDING)], unique=True)
    _ensure_index(vehicles, [("vehicle_id", ASCENDING)])
    _ensure_index(vehicles, [("organization", ASCENDING)])
    _ensure_index(vehicles, [("status_id", ASCENDING)])
    _ensure_index(vehicles, [("type_id", ASCENDING)])


def _create_aircraft_indexes(master_db: Database) -> None:
    aircraft = master_db[MasterCollections.AIRCRAFT]
    _ensure_index(aircraft, [("aircraft_record", ASCENDING)], unique=True)
    _ensure_index(aircraft, [("agency", ASCENDING)])
    _ensure_index(aircraft, [("status", ASCENDING)])
    _ensure_index(aircraft, [("aircraft_type", ASCENDING)])


def _create_equipment_indexes(master_db: Database) -> None:
    equipment = master_db[MasterCollections.EQUIPMENT]
    _ensure_index(equipment, [("equipment_record", ASCENDING)], unique=True)
    _ensure_index(equipment, [("agency", ASCENDING)])
    _ensure_index(equipment, [("status", ASCENDING)])
    _ensure_index(equipment, [("equipment_type", ASCENDING)])
