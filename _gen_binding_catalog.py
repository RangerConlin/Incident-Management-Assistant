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
    ("name",       "Channel Name"),
    ("function",   "Function"),
    ("rx_freq",    "RX Frequency"),
    ("tx_freq",    "TX Frequency"),
    ("rx_tone",    "RX Tone"),
    ("tx_tone",    "TX Tone"),
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
            "table": "narrative_entries",
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
    ("name",    "Name"),
    ("type",    "Type"),
    ("phone",   "Phone"),
    ("fax",     "Fax"),
    ("address", "Address"),
    ("city",    "City"),
    ("state",   "State"),
    ("zip",     "Zip"),
    ("contact", "Contact"),
    ("notes",   "Notes"),
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
    ("name",          "Name"),
    ("type",          "Type"),
    ("phone",         "Phone"),
    ("radio_channel", "Radio Channel"),
    ("address",       "Address"),
    ("city",          "City"),
    ("state",         "State"),
    ("zip",           "Zip"),
    ("notes",         "Notes"),
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
