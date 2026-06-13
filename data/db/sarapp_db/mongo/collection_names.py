"""
MongoDB collection name constants for all SARApp databases.

Centralizing names here prevents typos and makes renames straightforward.
Import from this module rather than writing collection name strings inline.

Three logical databases exist:
    sarapp_system              — server/app-level configuration and state
    sarapp_master              — agency-wide reference data (personnel, equipment, etc.)
    sarapp_incident_<id>       — per-incident operational data
"""


class SystemCollections:
    """Collection names for the sarapp_system database."""

    APP_SETTINGS = "app_settings"
    SERVER_IDENTITY = "server_identity"
    WORKSTATIONS = "workstations"
    SYNC_STATE = "sync_state"
    ACTIVE_INCIDENT = "active_incident"
    AUDIT_GLOBAL = "audit_global"


class MasterCollections:
    """Collection names for the sarapp_master database."""

    # Personnel — certifications embedded as array inside each personnel document
    PERSONNEL = "personnel"
    CERTIFICATION_TYPES = "certification_types"

    # Resources
    EQUIPMENT = "equipment"
    VEHICLES = "vehicles"
    AIRCRAFT = "aircraft"

    # Radio/comms — channels and comms resources are one collection
    RADIO_CHANNELS = "radio_channels"

    # Hazard typing library
    HAZARD_TYPES = "hazard_types"

    # Facilities
    HOSPITALS = "hospitals"

    # Reference / lookup tables
    RESOURCE_TYPES = "resource_types"
    RESOURCE_CAPABILITIES = "resource_capabilities"
    AGENCY_DIRECTORY = "agency_directory"

    # Templates
    FORM_TEMPLATES = "form_templates"
    INCIDENT_TEMPLATES = "incident_templates"
    MEETING_TEMPLATES = "meeting_templates"
    TASK_TYPES = "task_types"

    # Users and access
    USER_PROFILES = "user_profiles"
    ROLE_TEMPLATES = "role_templates"


class IncidentCollections:
    """Collection names for per-incident databases (sarapp_incident_<incident_id>)."""

    # Incident structure
    INCIDENT_PROFILE = "incident_profile"
    OPERATIONAL_PERIODS = "operational_periods"
    INCIDENT_OBJECTIVES = "incident_objectives"
    STRATEGIES = "strategies"  # formerly strategic_objectives

    # Teams — incident-specific team assignments and composition
    TEAMS = "teams"

    # Tasks — team, personnel, vehicle assignments, and narrative all embedded inside each task document
    TASKS = "tasks"

    # Resources
    RESOURCE_REQUESTS = "resource_requests"

    # Incident organization (ICS 203) — separate flat collections for CRUD
    ORG_POSITIONS = "org_positions"
    ORG_ASSIGNMENTS = "org_assignments"
    ORG_HISTORY = "org_history"
    ORG_TEMPLATES = "org_templates"
    ORG_SNAPSHOTS = "org_snapshots"

    # Check in/out — one collection covering personnel, vehicles, aircraft, equipment
    # Each document has a resource_type field to distinguish
    CHECK_IN_OUT = "check_in_out"

    # Communications
    COMMUNICATIONS_LOG = "communications_log"
    ICS_213_MESSAGES = "ics_213_messages"
    ICS_214_LOGS = "ics_214_logs"
    ICS_205_INSTANCES = "ics_205_instances"

    # Forms — completed forms only, one collection
    FORMS = "forms"

    # Hazards identified during this incident
    HAZARDS = "hazards"

    # Radio channels assigned to this incident (subset/override of master radio_channels)
    INCIDENT_CHANNELS = "incident_channels"

    # Resources checked in to the incident (vehicles, equipment — resource_type distinguishes)
    RESOURCES = "resources"

    # ICS 203 — incident organization (positions, units, assignments merged per version)
    INCIDENT_ORGANIZATION = "incident_organization"

    # ICS 214 — unit logs (stream = log header, entries embedded)
    UNIT_LOGS = "unit_logs"

    # Meetings (attendees and checklist items embedded)
    MEETINGS = "meetings"

    # Incident journal — freeform timestamped log entries (planning section notes)
    INCIDENT_JOURNAL = "incident_journal"

    # Supporting
    ATTACHMENTS = "attachments"
    AUDIT_LOGS = "audit_logs"
    STATUS_BOARD_SNAPSHOTS = "status_board_snapshots"
