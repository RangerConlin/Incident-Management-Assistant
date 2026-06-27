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
    INCIDENTS = "incidents"


class MasterCollections:
    """Collection names for the sarapp_master database."""

    # Personnel — certifications and org master data
    PERSONNEL = "personnel"
    CERTIFICATION_TYPES = "certification_types"
    CERTIFICATION_TAGS = "certification_tags"
    PERSONNEL_CERTIFICATIONS = "personnel_certifications"
    ORGANIZATION_TYPES = "organization_types"
    RANK_STRUCTURES = "rank_structures"
    ORGANIZATIONS = "organizations"
    RANKS = "ranks"
    ORGANIZATION_RANK_STRUCTURE_OVERRIDES = "organization_rank_structure_overrides"
    ORGANIZATION_AUDIT_LOG = "organization_audit_log"
    RANK_STRUCTURE_AUDIT_LOG = "rank_structure_audit_log"

    # Resources
    EQUIPMENT = "equipment"
    VEHICLES = "vehicles"
    AIRCRAFT = "aircraft"

    # Radio/comms — channels and comms resources are one collection
    RADIO_CHANNELS = "radio_channels"

    # Hazard typing library
    HAZARD_TYPES = "hazard_types"
    SAFETY_ANALYSIS_TEMPLATES = "safety_analysis_templates"

    # Facilities
    HOSPITALS = "hospitals"
    EMS_AGENCIES = "ems_agencies"

    # Reference / lookup tables
    INCIDENT_TYPES = "incident_types"
    RESOURCE_TYPES = "resource_types"
    RESOURCE_CAPABILITIES = "resource_capabilities"
    AGENCY_DIRECTORY = "agency_directory"

    # Templates
    FORM_FAMILIES = "form_families"
    FORM_TEMPLATES = "form_templates"
    FORM_TEMPLATE_VERSIONS = "form_template_versions"
    INCIDENT_TEMPLATES = "incident_templates"
    MEETING_TEMPLATES = "meeting_templates"
    TASK_TYPES = "task_types"
    TEAM_TYPES = "team_types"
    OBJECTIVE_TEMPLATES = "objective_templates"
    STRATEGY_TEMPLATES = "strategy_templates"
    CANNED_COMM_ENTRIES = "canned_comm_entries"

    # Users and access
    USERS = "users"
    USER_SESSIONS = "user_sessions"
    USER_PROFILES = "user_profiles"
    ROLE_TEMPLATES = "role_templates"


class IncidentCollections:
    """Collection names for per-incident databases (sarapp_incident_<incident_id>)."""

    # Incident structure
    INCIDENT_PROFILE = "incident_profile"
    OPERATIONAL_PERIODS = "operational_periods"
    INCIDENT_OBJECTIVES = "incident_objectives"
    STRATEGIES = "strategies"  # formerly strategic_objectives
    OBJECTIVE_STRATEGIES_TASK_LINKS = "objective_strategy_task_links"

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

    # Personnel check-in roster and history
    CHECKINS = "checkins"
    CHECKIN_HISTORY = "checkin_history"

    # Communications
    COMMUNICATIONS_LOG = "communications_log"
    COMMS_LOG_AUDIT = "comms_log_audit"
    COMMS_LOG_FILTERS = "comms_log_filters"
    ICS_213_MESSAGES = "ics_213_messages"
    ICS_214_LOGS = "ics_214_logs"
    ICS_205_INSTANCES = "ics_205_instances"
    ICS_206_AID_STATIONS = "ics_206_aid_stations"
    ICS_206_AMBULANCE_SERVICES = "ics_206_ambulance_services"
    ICS_206_HOSPITALS = "ics_206_hospitals"
    ICS_206_AIR_AMBULANCE = "ics_206_air_ambulance"
    ICS_206_MEDICAL_COMMS = "ics_206_medical_comms"
    ICS_206_PROCEDURES = "ics_206_procedures"
    ICS_206_SIGNATURES = "ics_206_signatures"

    # Public Information
    PIO_MESSAGES = "pio_messages"
    PIO_MESSAGE_REVISIONS = "pio_message_revisions"
    PIO_APPROVALS = "pio_approvals"
    PIO_MEDIA_LOG = "pio_media_log"
    PIO_MISINFORMATION_ITEMS = "pio_misinformation_items"
    PIO_MISINFORMATION_TIMELINE = "pio_misinformation_timeline"
    PIO_TALKING_POINTS = "pio_talking_points"
    PIO_TEMPLATES = "pio_templates"
    PIO_TEMPLATE_VERSIONS = "pio_template_versions"
    PIO_DISTRIBUTION_LOG = "pio_distribution_log"
    PIO_GENERATED_DOCUMENTS = "pio_generated_documents"

    # Forms — instances with embedded values; history/audit in separate collections
    FORMS = "forms"
    FORM_INSTANCE_REVISIONS = "form_instance_revisions"
    FORM_INSTANCE_AUDIT = "form_instance_audit"
    FORM_INSTANCE_EXPORTS = "form_instance_exports"
    FORM_INSTANCE_LINKS = "form_instance_links"

    # Hazards identified during this incident
    HAZARDS = "hazards"
    SAFETY_REPORTS = "safety_reports"
    MEDICAL_INCIDENTS = "medical_incidents"
    TRIAGE_ENTRIES = "triage_entries"
    HAZARD_ZONES = "hazard_zones"
    CAP_ORM_SUMMARIES = "cap_orm_summaries"
    CAP_ORM_FORMS = "cap_orm_forms"
    CAP_ORM_HAZARDS = "cap_orm_hazards"
    CAP_ORM_AUDIT = "cap_orm_audit"
    ICS_206_BUILDS = "ics_206_builds"

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

    # Personnel assigned/checked in to this incident
    INCIDENT_PERSONNEL = "incident_personnel"

    # Initial response planning
    INITIAL_RESPONSE_OVERVIEW = "initial_response_overview"
    INITIAL_HASTY_TASKS = "initial_hasty_tasks"
    INITIAL_REFLEX_ACTIONS = "initial_reflex_actions"

    # Planned event toolkit
    PLANNED_CAMPAIGNS = "planned_campaigns"
    PLANNED_EVENT_SCHEDULES = "planned_event_schedules"
    PLANNED_VENDORS = "planned_vendors"
    PLANNED_PERMITS = "planned_permits"
    PLANNED_SAFETY_REPORTS = "planned_safety_reports"
    PLANNED_TASKS = "planned_tasks"
    PLANNED_QUICK_ASSIGNMENTS = "planned_quick_assignments"
    PLANNED_HEALTH_INSPECTIONS = "planned_health_inspections"
    PLANNED_SCHEDULE_TRIGGERS = "planned_schedule_triggers"
    PLANNED_NOTIFICATIONS = "planned_notifications"

    # Logistics
    LOGISTICS_RESOURCE_STATUS_ITEMS = "logistics_resource_status_items"
    LOGISTICS_RESOURCE_REQUESTS = "logistics_resource_requests"
    FACILITIES = "facilities"

    # Operations (aliases to canonical task/team collections)
    OPERATIONS_TASKS = "tasks"
    OPERATIONS_TEAMS = "teams"
    OPERATIONS_TASK_DEBRIEFS = "task_debriefs"

    # Liaison
    LIAISON_AGENCIES = "liaison_agencies"
    LIAISON_CONTACTS = "liaison_contacts"
    LIAISON_INTERACTIONS = "liaison_interactions"
    LIAISON_AGENCY_REQUESTS = "liaison_agency_requests"
    LIAISON_RESOURCE_OFFERS = "liaison_resource_offers"
    LIAISON_FEEDBACK = "liaison_feedback"
    LIAISON_FOLLOWUP_ACTIONS = "liaison_followup_actions"
    LIAISON_RESTRICTIONS = "liaison_restrictions"
    LIAISON_AGREEMENTS = "liaison_agreements"

    # Intel — legacy (retained for migration compatibility)
    INTEL_CLUES = "intel_clues"
    INTEL_ENV_SNAPSHOTS = "intel_env_snapshots"
    INTEL_FORM_ENTRIES = "intel_form_entries"

    # Intel — All-Hazards Information Management (Module 7 redesign)
    INTEL_SUBJECTS = "intel_subjects"          # Human subjects (missing persons, witnesses, etc.)
    INTEL_LEADS = "intel_leads"                # Unverified tips and reports
    INTEL_ITEMS = "intel_items"                # Verified intel items with embedded observations[]
    INTEL_ASSESSMENTS = "intel_assessments"    # Finished analytical products
    INTEL_LOG = "intel_log"                    # Chronological activity log (ICS-214 equivalent)
    INTEL_REPORTS = "intel_reports"            # Frozen report snapshots

    # Work assignments (ICS-204 tactics / strategies)
    WORK_ASSIGNMENTS = "work_assignments"

    # GIS spatial features and links
    SPATIAL_FEATURES = "spatial_features"
    SPATIAL_FEATURE_LINKS = "spatial_feature_links"

    # ICS-208 Safety Message (one document per incident + op period)
    ICS_208_INSTANCES = "ics_208_instances"

    # Safety Incident (IWI) reports
    IWI_REPORTS = "iwi_reports"

    # Approvals — one instance per approvable entity, plus an append-only audit trail
    APPROVAL_INSTANCES = "approval_instances"
    APPROVAL_RECORDS = "approval_records"

    # Notifications — incident-scoped alert history
    NOTIFICATIONS = "notifications"

    # Supporting
    ATTACHMENTS = "attachments"
    AUDIT_LOGS = "audit_logs"
    STATUS_BOARD_SNAPSHOTS = "status_board_snapshots"

    # Finance/Admin — fuel pricing, forecasts, expenses, funding sources.
    # finance_approvals is module-specific rather than reusing
    # APPROVAL_INSTANCES/APPROVAL_RECORDS — see agents.md for the
    # consolidation note.
    FINANCE_FUEL_PRICE_PROFILES = "finance_fuel_price_profiles"
    FINANCE_FORECASTS = "finance_forecasts"
    FINANCE_FUEL_FORECAST_LINES = "finance_fuel_forecast_lines"
    FINANCE_FUNDING_SOURCES = "finance_funding_sources"
    FINANCE_EXPENSES = "finance_expenses"
    FINANCE_APPROVALS = "finance_approvals"
    FINANCE_ATTACHMENTS = "finance_attachments"
    WEATHER_DATA = "weather_data"
