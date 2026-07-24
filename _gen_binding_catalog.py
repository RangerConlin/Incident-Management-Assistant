"""Generate forms/binding_catalog.json from scratch."""

import json
from pathlib import Path

OUT = Path(__file__).parent / "forms" / "binding_catalog.json"

def _ordinal(n: int) -> str:
    sfx = {1: "st", 2: "nd", 3: "rd"}
    return f"{n}{sfx.get(n if n < 20 else n % 10, 'th')}"

entries = []

# ── Incident ─────────────────────────────────────────────────────────────────
INCIDENT_FIELDS = [
    ("name", "Incident Name"),
    ("number", "Incident Number"),
    ("type", "Incident Type"),
    ("description", "Incident Description"),
    ("icp_location", "ICP Location"),
    ("start_time", "Incident Start Time"),
    ("end_time", "Incident End Time"),
]
for col, label in INCIDENT_FIELDS:
    entries.append({
        "path": f"incident.{col}",
        "label": f"Incident — {label}",
        "category": "Incident",
        "source_type": "master_db",
        "table": "incidents",
        "column": col,
    })

# ── Operational Period ────────────────────────────────────────────────────────
OP_FIELDS = [
    ("number",     "Op Period Number"),
    ("start",      "Op Period Start (full datetime)"),
    ("end",        "Op Period End (full datetime)"),
    ("start_date", "Op Period Start Date (MM/DD/YYYY)"),
    ("start_time", "Op Period Start Time (HHMM)"),
    ("end_date",   "Op Period End Date (MM/DD/YYYY)"),
    ("end_time",   "Op Period End Time (HHMM)"),
]
for col, label in OP_FIELDS:
    entries.append({
        "path": f"op_period.{col}",
        "label": f"Op Period — {label}",
        "category": "Operational Period",
        "source_type": "incident_db",
        "table": "operationalperiods",
        "column": col,
    })

# ── Organization ─────────────────────────────────────────────────────────────
ORG_POSITIONS = [
    ("incident_commander",          "Incident Commander"),
    ("deputy_incident_commander",   "Deputy Incident Commander"),
    ("safety_officer",              "Safety Officer"),
    ("public_information_officer",  "Public Information Officer"),
    ("liaison_officer",             "Liaison Officer"),
    ("operations_section_chief",    "Operations Section Chief"),
    ("planning_section_chief",      "Planning Section Chief"),
    ("logistics_section_chief",     "Logistics Section Chief"),
    ("finance_admin_section_chief", "Finance/Admin Section Chief"),
    ("communications_unit_leader",  "Communications Unit Leader"),
    ("medical_unit_leader",         "Medical Unit Leader"),
    ("air_operations_branch_director", "Air Operations Branch Director"),
    ("ground_support_unit_leader",  "Ground Support Unit Leader"),
    ("food_unit_leader",            "Food Unit Leader"),
    ("facilities_unit_leader",      "Facilities Unit Leader"),
    ("supply_unit_leader",          "Supply Unit Leader"),
    ("situation_unit_leader",       "Situation Unit Leader"),
    ("resources_unit_leader",       "Resources Unit Leader"),
    ("documentation_unit_leader",   "Documentation Unit Leader"),
    ("demobilization_unit_leader",  "Demobilization Unit Leader"),
    ("staging_area_manager",        "Staging Area Manager"),
]
for key, title in ORG_POSITIONS:
    entries.append({
        "path": f"organization.{key}.name",
        "label": f"Organization — {title} Name",
        "category": "Organization",
        "source_type": "incident_db",
        "table": "position_assignments",
        "column": "display_name",
    })

# ── Prepared By ───────────────────────────────────────────────────────────────
for col, label in [("name", "Name"), ("position", "Position"), ("agency", "Agency"), ("date_time", "Date/Time")]:
    entries.append({
        "path": f"prepared_by.{col}",
        "label": f"Prepared By — {label}",
        "category": "Prepared By",
        "source_type": "computed",
        "table": None,
        "column": col,
    })

# ── Radio Channels ────────────────────────────────────────────────────────────
CHANNEL_FIELDS = [
    ("id",         "Row ID"),
    ("channel_id", "Channel ID"),
    ("master_id",  "Master Channel ID"),
    ("channel",    "Channel"),
    ("name",       "Channel Name"),
    ("function",   "Function"),
    ("band",       "Band"),
    ("system",     "System"),
    ("system_type","System Type"),
    ("rx_freq",    "RX Frequency"),
    ("tx_freq",    "TX Frequency"),
    ("rx_tone",    "RX Tone"),
    ("tx_tone",    "TX Tone"),
    ("squelch_type", "Squelch Type"),
    ("squelch_value", "Squelch Value"),
    ("repeater",   "Repeater"),
    ("offset",     "Offset"),
    ("encryption", "Encryption"),
    ("assignment_division", "Assignment Division"),
    ("assignment_team", "Assignment Team"),
    ("priority",   "Priority"),
    ("include_on_205", "Include On ICS 205"),
    ("sort_index", "Sort Index"),
    ("line_a",     "Line A"),
    ("line_c",     "Line C"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
    ("mode",       "Mode"),
    ("assignment", "Assignment"),
    ("remarks",    "Remarks"),
]
for i in range(8):
    ord_ = _ordinal(i + 1)
    for col, label in CHANNEL_FIELDS:
        entries.append({
            "path": f"channels.{i}.{col}",
            "label": f"Channel {i+1} ({ord_}) — {label}",
            "category": "Radio Channels",
            "source_type": "incident_db",
            "table": "incident_channels",
            "column": col,
            "index": i,
        })

# ── Teams ─────────────────────────────────────────────────────────────────────
TEAM_FIELDS = [
    ("name",          "Team Name"),
    ("status",        "Status"),
    ("leader_name",   "Leader Name"),
    ("resource_type", "Resource Type"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in TEAM_FIELDS:
        entries.append({
            "path": f"teams.{i}.{col}",
            "label": f"Team {i+1} ({ord_}) — {label}",
            "category": "Teams",
            "source_type": "incident_db",
            "table": "teams",
            "column": col,
            "index": i,
        })

# ── Tasks ─────────────────────────────────────────────────────────────────────
TASK_FIELDS = [
    ("task_id",        "Task ID"),
    ("title",          "Title"),
    ("location",       "Location"),
    ("priority",       "Priority"),
    ("status",         "Status"),
    ("assignment",     "Assignment"),
    ("team_leader",    "Team Leader"),
    ("team_phone",     "Team Phone"),
    ("radio_primary",  "Primary Radio"),
    ("radio_alternate","Alternate Radio"),
    ("radio_emergency","Emergency Radio"),
    ("category",       "Category"),
    ("task_type",      "Task Type"),
    ("due_time",       "Due Time"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in TASK_FIELDS:
        entries.append({
            "path": f"tasks.{i}.{col}",
            "label": f"Task {i+1} ({ord_}) — {label}",
            "category": "Tasks",
            "source_type": "incident_db",
            "table": "tasks",
            "column": col,
            "index": i,
        })

# ── SAR 104 Helpers ───────────────────────────────────────────────────────────
SAR104_SINGLE_FIELDS = [
    ("task.task_id", "Task — Task ID"),
    ("task.assignment", "Task — Assignment"),
    ("team.resource_type", "Team — Resource Type"),
    ("team.role", "Team — Role"),
    ("team.leader_name", "Team — Leader Name"),
    ("team.leader_agency", "Team — Leader Agency"),
    ("assignment.ground.previous_search_efforts", "Assignment — Previous Search Efforts"),
    ("assignment.ground.time_allocated", "Assignment — Time Allocated"),
    ("assignment.ground.size_of_assignment", "Assignment — Size of Assignment"),
    ("assignment.ground.transport_instructions", "Assignment — Transport Instructions"),
    ("radio_call", "Assignment — Radio Call"),
    ("equipment_issued", "Assignment — Equipment Issued"),
    ("briefer", "Assignment — Briefer"),
    ("time_briefed", "Assignment — Time Briefed"),
    ("time_out", "Assignment — Time Out"),
    ("time_in", "Assignment — Time In"),
    ("notes", "Assignment — Notes"),
    ("additional.names", "Assignment — Additional Names"),
    ("maps_attached", "Assignment — Maps Attached"),
    ("debrief_attached", "Assignment — Debrief Attached"),
]
for path, label in SAR104_SINGLE_FIELDS:
    entries.append({
        "path": path,
        "label": label,
        "category": "SAR 104",
        "source_type": "computed",
        "table": None,
        "column": path.rsplit(".", 1)[-1],
    })

for field_group, label_group in [
    ("responsive", "Responsive"),
    ("unresponsive", "Unresponsive"),
    ("clues", "Clues"),
]:
    for level in ("high", "medium", "low"):
        entries.append({
            "path": f"assignment.ground.expected_pod.{field_group}.{level}",
            "label": f"SAR 104 — Expected POD ({label_group}) {level.title()}",
            "category": "SAR 104",
            "source_type": "computed",
            "table": None,
            "column": level,
        })

for i in range(8):
    ord_ = _ordinal(i + 1)
    for col, label in [
        ("member_name", "Member Name"),
        ("member_agency", "Member Agency"),
        ("member_medic", "Member Medic"),
        ("member_role", "Member Role"),
    ]:
        entries.append({
            "path": f"team_members.{i}.{col}",
            "label": f"SAR 104 Team Members {i+1} ({ord_}) — {label}",
            "category": "SAR 104 Team Members",
            "source_type": "computed",
            "table": None,
            "column": col,
            "index": i,
        })

# ── Aircraft ──────────────────────────────────────────────────────────────────
AIRCRAFT_FIELDS = [
    ("tail_number",        "Tail Number"),
    ("callsign",           "Callsign"),
    ("type",               "Type"),
    ("make",               "Make"),
    ("model",              "Model"),
    ("base",               "Base"),
    ("current_location",   "Current Location"),
    ("status",             "Status"),
    ("organization",       "Organization"),
    ("fuel_type",          "Fuel Type"),
    ("range_nm",           "Range (NM)"),
    ("endurance_hr",       "Endurance (hr)"),
    ("cruise_kt",          "Cruise Speed (kt)"),
    ("crew_min",           "Crew Minimum"),
    ("crew_max",           "Crew Maximum"),
    ("payload_kg",         "Payload (kg)"),
    ("assigned_team_name", "Assigned Team"),
]
for i in range(5):
    ord_ = _ordinal(i + 1)
    for col, label in AIRCRAFT_FIELDS:
        entries.append({
            "path": f"aircraft.{i}.{col}",
            "label": f"Aircraft {i+1} ({ord_}) — {label}",
            "category": "Aviation",
            "source_type": "master_db",
            "table": "aircraft",
            "column": col,
            "index": i,
        })

# ── Personnel ─────────────────────────────────────────────────────────────────
PERSONNEL_FIELDS = [
    ("name",           "Name"),
    ("agency",         "Agency"),
    ("radio_id",       "Radio ID"),
    ("certifications", "Certifications"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in PERSONNEL_FIELDS:
        entries.append({
            "path": f"personnel.{i}.{col}",
            "label": f"Personnel {i+1} ({ord_}) — {label}",
            "category": "Personnel",
            "source_type": "master_db",
            "table": "personnel",
            "column": col,
            "index": i,
        })

# ── Objectives ────────────────────────────────────────────────────────────────
OBJECTIVE_FIELDS = [
    ("description",      "Description"),
    ("text",             "Text"),
    ("status",           "Status"),
    ("priority",         "Priority"),
    ("assigned_section", "Assigned Section"),
    ("owner_section",    "Owner Section"),
    ("due_time",         "Due Time"),
    ("code",             "Code"),
    ("display_order",    "Display Order"),
]
for i in range(20):
    ord_ = _ordinal(i + 1)
    for col, label in OBJECTIVE_FIELDS:
        entries.append({
            "path": f"objectives.{i}.{col}",
            "label": f"Objective {i+1} ({ord_}) — {label}",
            "category": "Objectives",
            "source_type": "incident_db",
            "table": "incident_objectives",
            "column": col,
            "index": i,
        })

# ── Subject (SAR) ─────────────────────────────────────────────────────────────
SUBJECT_FIELDS = [
    ("name",      "Name"),
    ("sex",       "Sex"),
    ("dob",       "Date of Birth"),
    ("race",      "Race"),
    ("lkp_place", "Last Known Place"),
    ("lkp_time",  "Last Known Time"),
]
for col, label in SUBJECT_FIELDS:
    entries.append({
        "path": f"subject.{col}",
        "label": f"Subject — {label}",
        "category": "Subject",
        "source_type": "incident_db",
        "table": "subject",
        "column": col,
    })

# ── Vehicles (incident) ───────────────────────────────────────────────────────
VEHICLE_FIELDS = [
    ("make",         "Make"),
    ("model",        "Model"),
    ("year",         "Year"),
    ("license_plate","License Plate"),
    ("capacity",     "Capacity"),
    ("organization", "Organization"),
]
for i in range(5):
    ord_ = _ordinal(i + 1)
    for col, label in VEHICLE_FIELDS:
        entries.append({
            "path": f"vehicles.{i}.{col}",
            "label": f"Vehicle {i+1} ({ord_}) — {label}",
            "category": "Vehicles",
            "source_type": "incident_db",
            "table": "vehicles",
            "column": col,
            "index": i,
        })

# ── Agency Contacts ───────────────────────────────────────────────────────────
CONTACT_FIELDS = [
    ("title",  "Title"),
    ("name",   "Name"),
    ("agency", "Agency"),
    ("phone",  "Phone"),
    ("email",  "Email"),
    ("notes",  "Notes"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in CONTACT_FIELDS:
        entries.append({
            "path": f"agency_contacts.{i}.{col}",
            "label": f"Agency Contact {i+1} ({ord_}) — {label}",
            "category": "Agency Contacts",
            "source_type": "incident_db",
            "table": "agency_contacts",
            "column": col,
            "index": i,
        })

# ── Liaison Agencies ──────────────────────────────────────────────────────────
LIAISON_AGENCY_FIELDS = [
    ("int_id", "ID"),
    ("name", "Agency Name"),
    ("agency_type", "Agency Type"),
    ("jurisdiction", "Jurisdiction"),
    ("current_status", "Current Status"),
    ("assigned_liaison", "Assigned Liaison"),
    ("last_contact", "Last Contact"),
    ("next_contact_due", "Next Contact Due"),
    ("priority", "Priority"),
    ("notes", "Notes"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in LIAISON_AGENCY_FIELDS:
        entries.append({
            "path": f"liaison_agencies.{i}.{col}",
            "label": f"Liaison Agency {i+1} ({ord_}) — {label}",
            "category": "Liaison Agencies",
            "source_type": "incident_db",
            "table": "liaison_agencies",
            "column": col,
            "index": i,
        })

# ── Liaison Contacts ──────────────────────────────────────────────────────────
LIAISON_CONTACT_FIELDS = [
    ("int_id", "ID"),
    ("agency_id", "Agency ID"),
    ("name", "Name"),
    ("title", "Title"),
    ("role", "Role"),
    ("agency", "Agency"),
    ("phone", "Phone"),
    ("email", "Email"),
    ("radio_channel", "Radio Channel"),
    ("preferred_contact", "Preferred Contact"),
    ("notes", "Notes"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in LIAISON_CONTACT_FIELDS:
        entries.append({
            "path": f"liaison_contacts.{i}.{col}",
            "label": f"Liaison Contact {i+1} ({ord_}) — {label}",
            "category": "Liaison Contacts",
            "source_type": "incident_db",
            "table": "liaison_contacts",
            "column": col,
            "index": i,
        })

# ── Liaison Interactions ──────────────────────────────────────────────────────
LIAISON_INTERACTION_FIELDS = [
    ("int_id", "ID"),
    ("agency_id", "Agency ID"),
    ("agency", "Agency"),
    ("contact_id", "Contact ID"),
    ("interaction_type", "Interaction Type"),
    ("occurred_at", "Occurred At"),
    ("subject", "Subject"),
    ("summary", "Summary"),
    ("followup_action", "Follow-up Action"),
    ("followup_assigned_to", "Follow-up Assigned To"),
    ("followup_due", "Follow-up Due"),
    ("entered_by", "Entered By"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
    ("objective_id", "Objective ID"),
    ("strategy_id", "Strategy ID"),
    ("task_id", "Task ID"),
    ("resource_request_id", "Resource Request ID"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in LIAISON_INTERACTION_FIELDS:
        entries.append({
            "path": f"liaison_interactions.{i}.{col}",
            "label": f"Liaison Interaction {i+1} ({ord_}) — {label}",
            "category": "Liaison Interactions",
            "source_type": "incident_db" if col not in {"agency"} else "computed",
            "table": "liaison_interactions" if col not in {"agency"} else None,
            "column": col,
            "index": i,
        })

# ── Liaison Feedback ──────────────────────────────────────────────────────────
LIAISON_FEEDBACK_FIELDS = [
    ("int_id", "ID"),
    ("agency_id", "Agency ID"),
    ("agency", "Agency"),
    ("contact_id", "Contact ID"),
    ("feedback_type", "Feedback Type"),
    ("priority", "Priority"),
    ("summary", "Summary"),
    ("requested_action", "Requested Action"),
    ("assigned_section", "Assigned Section"),
    ("assigned_to", "Assigned To"),
    ("status", "Status"),
    ("interaction_id", "Interaction ID"),
    ("objective_id", "Objective ID"),
    ("strategy_id", "Strategy ID"),
    ("task_id", "Task ID"),
    ("resource_request_id", "Resource Request ID"),
    ("validation_status", "Validation Status"),
    ("followup_due", "Follow-up Due"),
    ("entered_by", "Entered By"),
    ("entered_ts", "Entered Timestamp"),
    ("resolved_by", "Resolved By"),
    ("resolved_ts", "Resolved Timestamp"),
    ("resolution_notes", "Resolution Notes"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in LIAISON_FEEDBACK_FIELDS:
        entries.append({
            "path": f"liaison_feedback.{i}.{col}",
            "label": f"Liaison Feedback {i+1} ({ord_}) — {label}",
            "category": "Liaison Feedback",
            "source_type": "incident_db" if col not in {"agency"} else "computed",
            "table": "liaison_feedback" if col not in {"agency"} else None,
            "column": col,
            "index": i,
        })

# ── Liaison Agency Requests ───────────────────────────────────────────────────
LIAISON_REQUEST_FIELDS = [
    ("int_id", "ID"),
    ("agency_id", "Agency ID"),
    ("agency", "Agency"),
    ("contact_id", "Contact ID"),
    ("interaction_id", "Interaction ID"),
    ("description", "Description"),
    ("requested_by", "Requested By"),
    ("priority", "Priority"),
    ("status", "Status"),
    ("due_date", "Due Date"),
    ("resource_request_id", "Resource Request ID"),
    ("notes", "Notes"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in LIAISON_REQUEST_FIELDS:
        entries.append({
            "path": f"liaison_agency_requests.{i}.{col}",
            "label": f"Liaison Agency Request {i+1} ({ord_}) — {label}",
            "category": "Liaison Agency Requests",
            "source_type": "incident_db" if col not in {"agency"} else "computed",
            "table": "liaison_agency_requests" if col not in {"agency"} else None,
            "column": col,
            "index": i,
        })

# ── Liaison Resource Offers ───────────────────────────────────────────────────
LIAISON_OFFER_FIELDS = [
    ("int_id", "ID"),
    ("agency_id", "Agency ID"),
    ("agency", "Agency"),
    ("contact_id", "Contact ID"),
    ("interaction_id", "Interaction ID"),
    ("description", "Description"),
    ("offered_by", "Offered By"),
    ("quantity", "Quantity"),
    ("available_from", "Available From"),
    ("priority", "Priority"),
    ("status", "Status"),
    ("resource_request_id", "Resource Request ID"),
    ("notes", "Notes"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in LIAISON_OFFER_FIELDS:
        entries.append({
            "path": f"liaison_resource_offers.{i}.{col}",
            "label": f"Liaison Resource Offer {i+1} ({ord_}) — {label}",
            "category": "Liaison Resource Offers",
            "source_type": "incident_db" if col not in {"agency"} else "computed",
            "table": "liaison_resource_offers" if col not in {"agency"} else None,
            "column": col,
            "index": i,
        })

# ── Liaison Follow-up Actions ─────────────────────────────────────────────────
LIAISON_FOLLOWUP_FIELDS = [
    ("int_id", "ID"),
    ("agency_id", "Agency ID"),
    ("agency", "Agency"),
    ("contact_id", "Contact ID"),
    ("interaction_id", "Interaction ID"),
    ("feedback_id", "Feedback ID"),
    ("action_summary", "Action Summary"),
    ("assigned_to", "Assigned To"),
    ("due_at", "Due At"),
    ("status", "Status"),
    ("objective_id", "Objective ID"),
    ("strategy_id", "Strategy ID"),
    ("task_id", "Task ID"),
    ("resource_request_id", "Resource Request ID"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in LIAISON_FOLLOWUP_FIELDS:
        entries.append({
            "path": f"liaison_followup_actions.{i}.{col}",
            "label": f"Liaison Follow-up {i+1} ({ord_}) — {label}",
            "category": "Liaison Follow-up Actions",
            "source_type": "incident_db" if col not in {"agency"} else "computed",
            "table": "liaison_followup_actions" if col not in {"agency"} else None,
            "column": col,
            "index": i,
        })

# ── Liaison Restrictions ──────────────────────────────────────────────────────
LIAISON_RESTRICTION_FIELDS = [
    ("int_id", "ID"),
    ("agency_id", "Agency ID"),
    ("agency", "Agency"),
    ("restriction_type", "Restriction Type"),
    ("description", "Description"),
    ("effective_at", "Effective At"),
    ("expires_at", "Expires At"),
    ("status", "Status"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in LIAISON_RESTRICTION_FIELDS:
        entries.append({
            "path": f"liaison_restrictions.{i}.{col}",
            "label": f"Liaison Restriction {i+1} ({ord_}) — {label}",
            "category": "Liaison Restrictions",
            "source_type": "incident_db" if col not in {"agency"} else "computed",
            "table": "liaison_restrictions" if col not in {"agency"} else None,
            "column": col,
            "index": i,
        })

# ── Liaison Agreements ────────────────────────────────────────────────────────
LIAISON_AGREEMENT_FIELDS = [
    ("int_id", "ID"),
    ("agency_id", "Agency ID"),
    ("agency", "Agency"),
    ("agreement_type", "Agreement Type"),
    ("description", "Description"),
    ("effective_at", "Effective At"),
    ("expires_at", "Expires At"),
    ("status", "Status"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in LIAISON_AGREEMENT_FIELDS:
        entries.append({
            "path": f"liaison_agreements.{i}.{col}",
            "label": f"Liaison Agreement {i+1} ({ord_}) — {label}",
            "category": "Liaison Agreements",
            "source_type": "incident_db" if col not in {"agency"} else "computed",
            "table": "liaison_agreements" if col not in {"agency"} else None,
            "column": col,
            "index": i,
        })

# ── Narrative Entries ─────────────────────────────────────────────────────────
NARRATIVE_FIELDS = [
    ("timestamp",  "Timestamp"),
    ("narrative",  "Narrative"),
    ("entered_by", "Entered By"),
    ("team_num",   "Team Number"),
    ("critical",   "Critical"),
]
for i in range(20):
    ord_ = _ordinal(i + 1)
    for col, label in NARRATIVE_FIELDS:
        entries.append({
            "path": f"narrative.{i}.{col}",
            "label": f"Narrative Entry {i+1} ({ord_}) — {label}",
            "category": "Narrative",
            "source_type": "incident_db",
            "table": "ics_214_logs",
            "column": col,
            "index": i,
        })

# ── Communications Log ───────────────────────────────────────────────────────
COMM_LOG_FIELDS = [
    ("id", "Row ID"),
    ("comms_id", "Comms ID"),
    ("ts_utc", "UTC Timestamp"),
    ("ts_local", "Local Timestamp"),
    ("direction", "Direction"),
    ("priority", "Priority"),
    ("resource_id", "Resource ID"),
    ("resource_label", "Resource Label"),
    ("frequency", "Frequency"),
    ("band", "Band"),
    ("mode", "Mode"),
    ("from_unit", "From Unit"),
    ("to_unit", "To Unit"),
    ("message", "Message"),
    ("action_taken", "Action Taken"),
    ("follow_up_required", "Follow Up Required"),
    ("disposition", "Disposition"),
    ("operator_user_id", "Operator User ID"),
    ("operator_display_name", "Operator Name"),
    ("team_id", "Team ID"),
    ("task_id", "Task ID"),
    ("vehicle_id", "Vehicle ID"),
    ("personnel_id", "Personnel ID"),
    ("attachments", "Attachments"),
    ("geotag_lat", "Geo Latitude"),
    ("geotag_lon", "Geo Longitude"),
    ("notification_level", "Notification Level"),
    ("is_status_update", "Is Status Update"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]
for i in range(20):
    ord_ = _ordinal(i + 1)
    for col, label in COMM_LOG_FIELDS:
        entries.append({
            "path": f"comm_log.{i}.{col}",
            "label": f"Communications Log Entry {i+1} ({ord_}) — {label}",
            "category": "Communications Log",
            "source_type": "incident_db",
            "table": "communications_log",
            "column": col,
            "index": i,
        })

# ── Safety Hazards ───────────────────────────────────────────────────────────
HAZARD_FIELDS = [
    ("id", "ID"),
    ("incident_id", "Incident ID"),
    ("work_assignment_id", "Work Assignment ID"),
    ("hazard_type_id", "Hazard Type ID"),
    ("hazard_type_text", "Hazard"),
    ("risk_level", "Risk Level"),
    ("likelihood", "Likelihood"),
    ("severity", "Severity"),
    ("control_measure", "Control Measure"),
    ("mitigation_text", "Mitigation"),
    ("ppe_text", "PPE Required"),
    ("safety_message", "Safety Message"),
    ("is_resolved", "Resolved"),
    ("notes", "Notes"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]
for i in range(20):
    ord_ = _ordinal(i + 1)
    for col, label in HAZARD_FIELDS:
        entries.append({
            "path": f"hazards.{i}.{col}",
            "label": f"Hazard {i+1} ({ord_}) — {label}",
            "category": "Safety Hazards",
            "source_type": "incident_db",
            "table": "hazards",
            "column": col,
            "index": i,
        })

# ── Safety Reports ───────────────────────────────────────────────────────────
SAFETY_REPORT_FIELDS = [
    ("id", "ID"),
    ("incident_id", "Incident ID"),
    ("time", "Time"),
    ("location", "Location"),
    ("severity", "Severity"),
    ("notes", "Notes"),
    ("flagged", "Flagged"),
    ("reported_by", "Reported By"),
    ("team_id", "Team ID"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]
for i in range(20):
    ord_ = _ordinal(i + 1)
    for col, label in SAFETY_REPORT_FIELDS:
        entries.append({
            "path": f"safety_reports.{i}.{col}",
            "label": f"Safety Report {i+1} ({ord_}) — {label}",
            "category": "Safety Reports",
            "source_type": "incident_db",
            "table": "safety_reports",
            "column": col,
            "index": i,
        })

# ── Hazard Zones ─────────────────────────────────────────────────────────────
HAZARD_ZONE_FIELDS = [
    ("id", "ID"),
    ("incident_id", "Incident ID"),
    ("name", "Name"),
    ("coordinates_json", "Coordinates JSON"),
    ("geometry_wkt", "Geometry WKT"),
    ("feature_subtype", "Feature Subtype"),
    ("severity", "Severity"),
    ("description", "Description"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]
for i in range(20):
    ord_ = _ordinal(i + 1)
    for col, label in HAZARD_ZONE_FIELDS:
        entries.append({
            "path": f"hazard_zones.{i}.{col}",
            "label": f"Hazard Zone {i+1} ({ord_}) — {label}",
            "category": "Hazard Zones",
            "source_type": "incident_db",
            "table": "spatial_features",
            "column": col,
            "index": i,
        })

# ── CAP ORM Summary ──────────────────────────────────────────────────────────
CAP_ORM_SUMMARY_FIELDS = [
    ("id", "ID"),
    ("incident_id", "Incident ID"),
    ("form_type", "Form Type"),
    ("activity", "Activity"),
    ("participants_json", "Participants JSON"),
    ("hazards_json", "Hazards JSON"),
    ("mitigations_json", "Mitigations JSON"),
    ("residual_risk", "Residual Risk"),
    ("created_by", "Created By"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in CAP_ORM_SUMMARY_FIELDS:
        entries.append({
            "path": f"cap_orm_summaries.{i}.{col}",
            "label": f"CAP ORM Summary {i+1} ({ord_}) — {label}",
            "category": "CAP ORM Summaries",
            "source_type": "incident_db",
            "table": "cap_orm_summaries",
            "column": col,
            "index": i,
        })

# ── CAP ORM Form ─────────────────────────────────────────────────────────────
CAP_ORM_FORM_FIELDS = [
    ("id", "ID"),
    ("incident_id", "Incident ID"),
    ("op_period", "Operational Period"),
    ("activity", "Activity"),
    ("prepared_by_id", "Prepared By ID"),
    ("date_iso", "Date"),
    ("highest_residual_risk", "Highest Residual Risk"),
    ("status", "Status"),
    ("approval_blocked", "Approval Blocked"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]
for col, label in CAP_ORM_FORM_FIELDS:
    entries.append({
        "path": f"cap_orm_form.{col}",
        "label": f"CAP ORM Form — {label}",
        "category": "CAP ORM Form",
        "source_type": "incident_db",
        "table": "cap_orm_forms",
        "column": col,
    })

# ── CAP ORM Hazards ──────────────────────────────────────────────────────────
CAP_ORM_HAZARD_FIELDS = [
    ("id", "ID"),
    ("form_id", "Form ID"),
    ("sub_activity", "Sub-Activity"),
    ("hazard_outcome", "Hazard / Outcome"),
    ("initial_risk", "Initial Risk"),
    ("control_text", "Control Text"),
    ("residual_risk", "Residual Risk"),
    ("implement_how", "Implement How"),
    ("implement_who", "Implement Who"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]
for i in range(20):
    ord_ = _ordinal(i + 1)
    for col, label in CAP_ORM_HAZARD_FIELDS:
        entries.append({
            "path": f"cap_orm_hazards.{i}.{col}",
            "label": f"CAP ORM Hazard {i+1} ({ord_}) — {label}",
            "category": "CAP ORM Hazards",
            "source_type": "incident_db",
            "table": "cap_orm_hazards",
            "column": col,
            "index": i,
        })

# ── CAP ORM Audit ────────────────────────────────────────────────────────────
CAP_ORM_AUDIT_FIELDS = [
    ("incident_id", "Incident ID"),
    ("entity", "Entity"),
    ("entity_id", "Entity ID"),
    ("action", "Action"),
    ("field", "Field"),
    ("old_value", "Old Value"),
    ("new_value", "New Value"),
    ("ts_iso", "Timestamp"),
]
for i in range(20):
    ord_ = _ordinal(i + 1)
    for col, label in CAP_ORM_AUDIT_FIELDS:
        entries.append({
            "path": f"cap_orm_audit.{i}.{col}",
            "label": f"CAP ORM Audit {i+1} ({ord_}) — {label}",
            "category": "CAP ORM Audit",
            "source_type": "incident_db",
            "table": "cap_orm_audit",
            "column": col,
            "index": i,
        })

# ── ICS 208 ──────────────────────────────────────────────────────────────────
ICS_208_FIELDS = [
    ("incident_id", "Incident ID"),
    ("op_period", "Operational Period"),
    ("op_period_from", "Operational Period From"),
    ("op_period_to", "Operational Period To"),
    ("safety_message", "Safety Message"),
    ("site_safety_plan_required", "Site Safety Plan Required"),
    ("site_safety_plan_location", "Site Safety Plan Location"),
    ("prepared_by_name", "Prepared By Name"),
    ("prepared_by_position", "Prepared By Position"),
    ("prepared_by_datetime", "Prepared By Date/Time"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]
for col, label in ICS_208_FIELDS:
    entries.append({
        "path": f"ics_208.{col}",
        "label": f"ICS 208 — {label}",
        "category": "ICS 208",
        "source_type": "incident_db",
        "table": "ics_208_instances",
        "column": col,
    })

# ── ICS 215A Rows ────────────────────────────────────────────────────────────
ICS_215A_ROW_FIELDS = [
    ("work_assignment_id", "Work Assignment ID"),
    ("branch_div_group", "Branch / Division / Group"),
    ("work_assignment", "Work Assignment"),
    ("assignment_number", "Assignment Number"),
    ("assignment_name", "Assignment Name"),
    ("location", "Location"),
    ("hazard_id", "Hazard ID"),
    ("hazard", "Hazard"),
    ("category", "Category"),
    ("risk_level", "Risk Level"),
    ("likelihood", "Likelihood"),
    ("severity", "Severity"),
    ("control_measure", "Control Measure"),
    ("mitigation_text", "Mitigation"),
    ("ppe_text", "PPE"),
    ("resolved", "Resolved"),
    ("notes", "Notes"),
]
for i in range(20):
    ord_ = _ordinal(i + 1)
    for col, label in ICS_215A_ROW_FIELDS:
        entries.append({
            "path": f"ics_215a_rows.{i}.{col}",
            "label": f"ICS 215A Row {i+1} ({ord_}) — {label}",
            "category": "ICS 215A",
            "source_type": "computed",
            "table": "hazards",
            "column": col,
            "index": i,
        })

# ── IWI Reports ──────────────────────────────────────────────────────────────
IWI_FIELDS = [
    ("id", "ID"),
    ("form_number", "Form Number"),
    ("incident_id", "Incident ID"),
    ("status", "Status"),
    ("op_period", "Operational Period"),
    ("date_of_occurrence", "Date of Occurrence"),
    ("day_of_event", "Day of Event"),
    ("time_of_occurrence", "Time of Occurrence"),
    ("time_reported", "Time Reported"),
    ("reported_by", "Reported By"),
    ("location_general", "General Location"),
    ("location_zone", "Zone"),
    ("location_sector", "Sector"),
    ("location_specific", "Specific Location"),
    ("incident_types", "Incident Types"),
    ("incident_type_other", "Incident Type Other"),
    ("actual_outcome", "Actual Outcome"),
    ("actual_severity", "Actual Severity"),
    ("activity_impact", "Activity Impact"),
    ("activity_suspension_ref", "Activity Suspension Ref"),
    ("conditions", "Conditions"),
    ("persons_involved", "Persons Involved"),
    ("injury_details", "Injury Details"),
    ("equipment", "Equipment"),
    ("sequence_of_events", "Sequence Of Events"),
    ("narrative", "Narrative"),
    ("contributing_factors", "Contributing Factors"),
    ("immediate_actions", "Immediate Actions"),
    ("notifications", "Notifications"),
    ("corrective_actions", "Corrective Actions"),
    ("escalation_decision", "Escalation Decision"),
    ("escalation_rationale", "Escalation Rationale"),
    ("witnesses", "Witnesses"),
    ("prepared_by", "Prepared By"),
    ("signoffs", "Signoffs"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in IWI_FIELDS:
        entries.append({
            "path": f"iwi_reports.{i}.{col}",
            "label": f"IWI Report {i+1} ({ord_}) — {label}",
            "category": "IWI Reports",
            "source_type": "incident_db",
            "table": "iwi_reports",
            "column": col,
            "index": i,
        })

# ── Hazard Types ─────────────────────────────────────────────────────────────
HAZARD_TYPE_FIELDS = [
    ("id", "ID"),
    ("hazard_type_id", "Hazard Type ID"),
    ("name", "Name"),
    ("display_name", "Display Name"),
    ("category", "Category"),
    ("source", "Source"),
    ("owner_agency", "Owner Agency"),
    ("description", "Description"),
    ("default_risk_level", "Default Risk Level"),
    ("default_likelihood", "Default Likelihood"),
    ("default_severity", "Default Severity"),
    ("default_control_measure", "Default Control Measure"),
    ("default_ppe", "Default PPE"),
    ("default_safety_message", "Default Safety Message"),
    ("is_active", "Is Active"),
    ("notes", "Notes"),
    ("created_by", "Created By"),
    ("updated_by", "Updated By"),
    ("aliases", "Aliases"),
    ("mitigations", "Mitigations"),
    ("ppe_items", "PPE Items"),
    ("references", "References"),
    ("resource_defaults", "Resource Defaults"),
    ("mitigation_count", "Mitigation Count"),
    ("ppe_preview", "PPE Preview"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]
for i in range(20):
    ord_ = _ordinal(i + 1)
    for col, label in HAZARD_TYPE_FIELDS:
        entries.append({
            "path": f"hazard_types.{i}.{col}",
            "label": f"Hazard Type {i+1} ({ord_}) — {label}",
            "category": "Hazard Types",
            "source_type": "master_db",
            "table": "hazard_types",
            "column": col,
            "index": i,
        })

# ── Safety Analysis Templates ────────────────────────────────────────────────
SAFETY_TEMPLATE_FIELDS = [
    ("template_id", "Template ID"),
    ("name", "Name"),
    ("description", "Description"),
    ("scenario_type", "Scenario Type"),
    ("target_forms", "Target Forms"),
    ("hazard_entries", "Hazard Entries"),
    ("is_active", "Is Active"),
    ("notes", "Notes"),
    ("created_by", "Created By"),
    ("updated_by", "Updated By"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]
for i in range(20):
    ord_ = _ordinal(i + 1)
    for col, label in SAFETY_TEMPLATE_FIELDS:
        entries.append({
            "path": f"safety_analysis_templates.{i}.{col}",
            "label": f"Safety Template {i+1} ({ord_}) — {label}",
            "category": "Safety Analysis Templates",
            "source_type": "master_db",
            "table": "safety_analysis_templates",
            "column": col,
            "index": i,
        })

# ── Meetings ──────────────────────────────────────────────────────────────────
MEETING_FIELDS = [
    ("title",        "Title"),
    ("meeting_date", "Meeting Date"),
    ("start_time",   "Start Time"),
    ("end_time",     "End Time"),
    ("location",     "Location"),
    ("owner",        "Owner"),
    ("status",       "Status"),
]
for i in range(5):
    ord_ = _ordinal(i + 1)
    for col, label in MEETING_FIELDS:
        entries.append({
            "path": f"meetings.{i}.{col}",
            "label": f"Meeting {i+1} ({ord_}) — {label}",
            "category": "Meetings",
            "source_type": "incident_db",
            "table": "meetings",
            "column": col,
            "index": i,
        })

# ── Equipment (master) ────────────────────────────────────────────────────────
EQUIPMENT_FIELDS = [
    ("name",          "Name"),
    ("type",          "Type"),
    ("serial_number", "Serial Number"),
    ("condition",     "Condition"),
    ("notes",         "Notes"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in EQUIPMENT_FIELDS:
        entries.append({
            "path": f"equipment.{i}.{col}",
            "label": f"Equipment {i+1} ({ord_}) — {label}",
            "category": "Equipment",
            "source_type": "master_db",
            "table": "equipment",
            "column": col,
            "index": i,
        })

# ── Hospitals (master) ────────────────────────────────────────────────────────
HOSPITAL_FIELDS = [
    ("id", "ID"),
    ("hospital_id", "Hospital ID"),
    ("name", "Name"),
    ("type", "Type"),
    ("code", "Code"),
    ("phone", "Phone"),
    ("phone_er", "ER Phone"),
    ("phone_switchboard", "Switchboard Phone"),
    ("fax", "Fax"),
    ("email", "Email"),
    ("address", "Address"),
    ("city", "City"),
    ("state", "State"),
    ("zip", "Zip"),
    ("contact", "Contact"),
    ("contact_name", "Contact Name"),
    ("helipad", "Helipad"),
    ("burn_center", "Burn Center"),
    ("pediatric_capability", "Pediatric Capability"),
    ("adult_trauma_level", "Adult Trauma Level"),
    ("pediatric_trauma_level", "Pediatric Trauma Level"),
    ("trauma_level_display", "Trauma Level Display"),
    ("travel_time_min", "Travel Time (Minutes)"),
    ("bed_available", "Beds Available"),
    ("diversion_status", "Diversion Status"),
    ("ambulance_radio_channel", "Ambulance Radio Channel"),
    ("lat", "Latitude"),
    ("lon", "Longitude"),
    ("notes", "Notes"),
    ("is_active", "Is Active"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in HOSPITAL_FIELDS:
        entries.append({
            "path": f"hospitals.{i}.{col}",
            "label": f"Hospital {i+1} ({ord_}) — {label}",
            "category": "Hospitals",
            "source_type": "master_db",
            "table": "hospitals",
            "column": col,
            "index": i,
        })

# ── EMS Agencies (master) ─────────────────────────────────────────────────────
EMS_FIELDS = [
    ("id", "ID"),
    ("name", "Name"),
    ("type", "Type"),
    ("service_level", "Service Level"),
    ("service_level_label", "Service Level Label"),
    ("phone", "Phone"),
    ("radio_channel", "Radio Channel"),
    ("address", "Address"),
    ("city", "City"),
    ("state", "State"),
    ("zip", "Zip"),
    ("lat", "Latitude"),
    ("lon", "Longitude"),
    ("notes", "Notes"),
    ("default_on_206", "Default On ICS 206"),
    ("is_active", "Is Active"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in EMS_FIELDS:
        entries.append({
            "path": f"ems_agencies.{i}.{col}",
            "label": f"EMS Agency {i+1} ({ord_}) — {label}",
            "category": "EMS Agencies",
            "source_type": "master_db",
            "table": "ems_agencies",
            "column": col,
            "index": i,
        })

# ── ICS 206 Aid Stations ─────────────────────────────────────────────────────
ICS206_AID_STATION_FIELDS = [
    ("id", "ID"),
    ("op_period", "Operational Period"),
    ("name", "Name"),
    ("type", "Type"),
    ("level", "Level"),
    ("is_24_7", "24/7"),
    ("notes", "Notes"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in ICS206_AID_STATION_FIELDS:
        entries.append({
            "path": f"ics_206_aid_stations.{i}.{col}",
            "label": f"ICS 206 Aid Station {i+1} ({ord_}) — {label}",
            "category": "ICS 206 Aid Stations",
            "source_type": "incident_db",
            "table": "ics_206_aid_stations",
            "column": col,
            "index": i,
        })

# ── ICS 206 Ambulance Services ───────────────────────────────────────────────
ICS206_AMBULANCE_FIELDS = [
    ("id", "ID"),
    ("op_period", "Operational Period"),
    ("name", "Name"),
    ("type", "Type"),
    ("service_level", "Service Level"),
    ("service_level_label", "Service Level Label"),
    ("phone", "Phone"),
    ("location", "Location"),
    ("notes", "Notes"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in ICS206_AMBULANCE_FIELDS:
        entries.append({
            "path": f"ics_206_ambulance_services.{i}.{col}",
            "label": f"ICS 206 Ambulance Service {i+1} ({ord_}) — {label}",
            "category": "ICS 206 Ambulance Services",
            "source_type": "incident_db",
            "table": "ics_206_ambulance_services",
            "column": col,
            "index": i,
        })

# ── ICS 206 Hospitals ────────────────────────────────────────────────────────
ICS206_HOSPITAL_FIELDS = [
    ("id", "ID"),
    ("hospital_id", "Hospital ID"),
    ("op_period", "Operational Period"),
    ("name", "Name"),
    ("type", "Type"),
    ("code", "Code"),
    ("phone", "Phone"),
    ("phone_er", "ER Phone"),
    ("phone_switchboard", "Switchboard Phone"),
    ("fax", "Fax"),
    ("email", "Email"),
    ("address", "Address"),
    ("city", "City"),
    ("state", "State"),
    ("zip", "Zip"),
    ("contact", "Contact"),
    ("contact_name", "Contact Name"),
    ("helipad", "Helipad"),
    ("burn_center", "Burn Center"),
    ("pediatric_capability", "Pediatric Capability"),
    ("adult_trauma_level", "Adult Trauma Level"),
    ("pediatric_trauma_level", "Pediatric Trauma Level"),
    ("trauma_level_display", "Trauma Level Display"),
    ("travel_time_min", "Travel Time (Minutes)"),
    ("bed_available", "Beds Available"),
    ("diversion_status", "Diversion Status"),
    ("ambulance_radio_channel", "Ambulance Radio Channel"),
    ("lat", "Latitude"),
    ("lon", "Longitude"),
    ("notes", "Notes"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in ICS206_HOSPITAL_FIELDS:
        entries.append({
            "path": f"ics_206_hospitals.{i}.{col}",
            "label": f"ICS 206 Hospital {i+1} ({ord_}) — {label}",
            "category": "ICS 206 Hospitals",
            "source_type": "incident_db",
            "table": "ics_206_hospitals",
            "column": col,
            "index": i,
        })

# ── ICS 206 Air Ambulance ────────────────────────────────────────────────────
ICS206_AIR_AMBULANCE_FIELDS = [
    ("id", "ID"),
    ("op_period", "Operational Period"),
    ("name", "Name"),
    ("phone", "Phone"),
    ("base", "Base"),
    ("contact", "Contact"),
    ("notes", "Notes"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in ICS206_AIR_AMBULANCE_FIELDS:
        entries.append({
            "path": f"ics_206_air_ambulance.{i}.{col}",
            "label": f"ICS 206 Air Ambulance {i+1} ({ord_}) — {label}",
            "category": "ICS 206 Air Ambulance",
            "source_type": "incident_db",
            "table": "ics_206_air_ambulance",
            "column": col,
            "index": i,
        })

# ── ICS 206 Medical Comms ────────────────────────────────────────────────────
ICS206_MEDICAL_COMMS_FIELDS = [
    ("id", "ID"),
    ("op_period", "Operational Period"),
    ("channel", "Channel"),
    ("function", "Function"),
    ("frequency", "Frequency"),
    ("mode", "Mode"),
    ("notes", "Notes"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in ICS206_MEDICAL_COMMS_FIELDS:
        entries.append({
            "path": f"ics_206_medical_comms.{i}.{col}",
            "label": f"ICS 206 Medical Comms {i+1} ({ord_}) — {label}",
            "category": "ICS 206 Medical Comms",
            "source_type": "incident_db",
            "table": "ics_206_medical_comms",
            "column": col,
            "index": i,
        })

# ── ICS 206 Procedures ───────────────────────────────────────────────────────
ICS206_PROCEDURE_FIELDS = [
    ("id", "ID"),
    ("op_period", "Operational Period"),
    ("content", "Content"),
]
for col, label in ICS206_PROCEDURE_FIELDS:
    entries.append({
        "path": f"ics_206_procedures.{col}",
        "label": f"ICS 206 Procedures — {label}",
        "category": "ICS 206 Procedures",
        "source_type": "incident_db",
        "table": "ics_206_procedures",
        "column": col,
    })

# ── ICS 206 Signatures ───────────────────────────────────────────────────────
ICS206_SIGNATURE_FIELDS = [
    ("id", "ID"),
    ("op_period", "Operational Period"),
    ("prepared_by", "Prepared By"),
    ("position", "Position"),
    ("approved_by", "Approved By"),
    ("date", "Date"),
]
for col, label in ICS206_SIGNATURE_FIELDS:
    entries.append({
        "path": f"ics_206_signatures.{col}",
        "label": f"ICS 206 Signatures — {label}",
        "category": "ICS 206 Signatures",
        "source_type": "incident_db",
        "table": "ics_206_signatures",
        "column": col,
    })

# ── Comms Resources (master) ──────────────────────────────────────────────────
COMMS_FIELDS = [
    ("alpha_tag", "Alpha Tag"),
    ("function",  "Function"),
    ("freq_rx",   "RX Frequency"),
    ("rx_tone",   "RX Tone"),
    ("freq_tx",   "TX Frequency"),
    ("tx_tone",   "TX Tone"),
    ("system",    "System"),
    ("mode",      "Mode"),
    ("notes",     "Notes"),
]
for i in range(10):
    ord_ = _ordinal(i + 1)
    for col, label in COMMS_FIELDS:
        entries.append({
            "path": f"comms_resources.{i}.{col}",
            "label": f"Comms Resource {i+1} ({ord_}) — {label}",
            "category": "Comms Resources",
            "source_type": "master_db",
            "table": "comms_resources",
            "column": col,
            "index": i,
        })

# ── Resource Types (master) ───────────────────────────────────────────────────
RT_FIELDS = [
    ("name",                 "Name"),
    ("planning_display_name","Planning Display Name"),
    ("category",             "Category"),
    ("description",          "Description"),
    ("typical_team_size",    "Typical Team Size"),
]
for i in range(20):
    ord_ = _ordinal(i + 1)
    for col, label in RT_FIELDS:
        entries.append({
            "path": f"resource_types.{i}.{col}",
            "label": f"Resource Type {i+1} ({ord_}) — {label}",
            "category": "Resource Types",
            "source_type": "master_db",
            "table": "resource_types",
            "column": col,
            "index": i,
        })

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Wrote {len(entries)} entries to {OUT}")
