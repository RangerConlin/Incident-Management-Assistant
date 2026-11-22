"""Generate a complete fake incident for demo purposes.

Creates master catalog personnel/equipment, an incident, two operational
periods, checks catalog entries into the incident, builds teams, tasks,
task narrative entries, and planning work assignments linked back to the
tasks — a full, walkable, multi-period SAR scenario for demos.

This talks to a *running* server over HTTP using the same API every
client uses (no direct Mongo access), so every write goes through the
normal validation/business logic in server/sarapp_db/sarapp_db/api/routers/.

Catalog personnel/equipment lookups are idempotent (looked up by
person_id / equipment_id before creating), so re-running this script to
extend the roster will not fail on existing entries. The incident itself
is always created fresh with a new number.

Usage:
    python -m services.lan_server.server_manager --port 8765   # in one terminal
    python tools/scripts/generate_demo_incident.py              # in another

    # Point at a different server, or pick your own incident number:
    python tools/scripts/generate_demo_incident.py --base-url http://localhost:8765 --number DEMO-SAR-042
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

import httpx

START_TIME = datetime(2026, 11, 15, 6, 0, 0, tzinfo=timezone.utc)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def at(minutes: int) -> str:
    return iso(START_TIME + timedelta(minutes=minutes))


# ---------------------------------------------------------------------------
# Master catalog
# ---------------------------------------------------------------------------

PERSONNEL = [
    # Command staff
    {"name": "Dana Whitfield", "rank": "Incident Commander", "callsign": "Command 1",
     "primary_role": "Incident Commander", "phone": "555-0101", "email": "dwhitfield@example.org",
     "organization": "County SAR", "person_id": "P-1001", "is_medic": False},
    {"name": "Marcus Oyelaran", "rank": "Operations Section Chief", "callsign": "Ops 1",
     "primary_role": "Operations Section Chief", "phone": "555-0102", "email": "moyelaran@example.org",
     "organization": "County SAR", "person_id": "P-1002", "is_medic": False},
    {"name": "Priya Narayanan", "rank": "Planning Section Chief", "callsign": "Plans 1",
     "primary_role": "Planning Section Chief", "phone": "555-0103", "email": "pnarayanan@example.org",
     "organization": "County SAR", "person_id": "P-1003", "is_medic": False},
    {"name": "Hector Villarreal", "rank": "Safety Officer", "callsign": "Safety 1",
     "primary_role": "Safety Officer", "phone": "555-0104", "email": "hvillarreal@example.org",
     "organization": "County SAR", "person_id": "P-1004", "is_medic": False},
    {"name": "Renata Souza", "rank": "Logistics Section Chief", "callsign": "Log 1",
     "primary_role": "Logistics Section Chief", "phone": "555-0111", "email": "rsouza@example.org",
     "organization": "County SAR", "person_id": "P-1011", "is_medic": False},
    {"name": "Felix Ndiaye", "rank": "Finance/Admin Section Chief", "callsign": "Fin 1",
     "primary_role": "Finance/Admin Section Chief", "phone": "555-0112", "email": "fndiaye@example.org",
     "organization": "County SAR", "person_id": "P-1012", "is_medic": False},
    {"name": "Abigail Stroud", "rank": "Public Information Officer", "callsign": "PIO 1",
     "primary_role": "Public Information Officer", "phone": "555-0113", "email": "astroud@example.org",
     "organization": "County SAR", "person_id": "P-1013", "is_medic": False},
    {"name": "Walter Begay", "rank": "Liaison Officer", "callsign": "Liaison 1",
     "primary_role": "Agency Liaison", "phone": "555-0114", "email": "wbegay@example.org",
     "organization": "County SAR", "person_id": "P-1014", "is_medic": False},
    {"name": "Sumiko Kagawa", "rank": "Communications Unit Leader", "callsign": "Comms 1",
     "primary_role": "Communications Unit Leader", "phone": "555-0115", "email": "skagawa@example.org",
     "organization": "County SAR", "person_id": "P-1015", "is_medic": False},
    # Ground teams
    {"name": "Grace Lindqvist", "rank": "Team Leader", "callsign": "Alpha 1",
     "primary_role": "Ground Team Leader", "phone": "555-0105", "email": "glindqvist@example.org",
     "organization": "County SAR", "person_id": "P-1005", "is_medic": False},
    {"name": "Omar Delacroix", "rank": "Searcher", "callsign": "Alpha 2",
     "primary_role": "Ground Searcher", "phone": "555-0106", "email": "odelacroix@example.org",
     "organization": "County SAR", "person_id": "P-1006", "is_medic": True},
    {"name": "Yuki Tanabe", "rank": "Team Leader", "callsign": "Bravo 1",
     "primary_role": "Ground Team Leader", "phone": "555-0107", "email": "ytanabe@example.org",
     "organization": "County SAR", "person_id": "P-1007", "is_medic": False},
    {"name": "Lena Brodský", "rank": "Searcher", "callsign": "Bravo 2",
     "primary_role": "Ground Searcher", "phone": "555-0108", "email": "lbrodsky@example.org",
     "organization": "County SAR", "person_id": "P-1008", "is_medic": False},
    {"name": "Victor Kowalczyk", "rank": "Team Leader", "callsign": "Charlie 1",
     "primary_role": "Ground Team Leader", "phone": "555-0116", "email": "vkowalczyk@example.org",
     "organization": "County SAR", "person_id": "P-1016", "is_medic": False},
    {"name": "Ines Albrecht", "rank": "Searcher", "callsign": "Charlie 2",
     "primary_role": "Ground Searcher", "phone": "555-0117", "email": "ialbrecht@example.org",
     "organization": "County SAR", "person_id": "P-1017", "is_medic": False},
    {"name": "Desmond Okafor", "rank": "Team Leader", "callsign": "Delta 1",
     "primary_role": "Ground Team Leader", "phone": "555-0118", "email": "dokafor@example.org",
     "organization": "County SAR", "person_id": "P-1018", "is_medic": False},
    {"name": "Hannah Vuković", "rank": "Searcher", "callsign": "Delta 2",
     "primary_role": "Ground Searcher", "phone": "555-0119", "email": "hvukovic@example.org",
     "organization": "County SAR", "person_id": "P-1019", "is_medic": False},
    # K9
    {"name": "Caleb Ferreira", "rank": "K9 Handler", "callsign": "K9-1",
     "primary_role": "K9 Team Leader", "phone": "555-0109", "email": "cferreira@example.org",
     "organization": "County SAR K9 Unit", "person_id": "P-1009", "is_medic": False},
    {"name": "Marisol Quintana", "rank": "K9 Handler", "callsign": "K9-2",
     "primary_role": "K9 Team Leader", "phone": "555-0120", "email": "mquintana@example.org",
     "organization": "County SAR K9 Unit", "person_id": "P-1020", "is_medic": False},
    # Air
    {"name": "Noelle Ashworth", "rank": "Drone Pilot", "callsign": "Air 1",
     "primary_role": "sUAS Pilot", "phone": "555-0110", "email": "nashworth@example.org",
     "organization": "County SAR Air Ops", "person_id": "P-1010", "is_medic": False},
    {"name": "Trevor Lindgren", "rank": "Drone Pilot", "callsign": "Air 2",
     "primary_role": "sUAS Pilot", "phone": "555-0121", "email": "tlindgren@example.org",
     "organization": "County SAR Air Ops", "person_id": "P-1021", "is_medic": False},
    # Medical
    {"name": "Aisha Rahman", "rank": "EMS Medical Lead", "callsign": "Medic 1",
     "primary_role": "EMS Medical Lead", "phone": "555-0122", "email": "arahman@example.org",
     "organization": "County EMS", "person_id": "P-1022", "is_medic": True},
]

EQUIPMENT = [
    {"name": "ATV Unit 3", "type": "Vehicle - ATV", "serial_number": "ATV-003", "equipment_id": "EQ-2001"},
    {"name": "ATV Unit 4", "type": "Vehicle - ATV", "serial_number": "ATV-004", "equipment_id": "EQ-2002"},
    {"name": "UTV Ranger 1", "type": "Vehicle - UTV", "serial_number": "UTV-001", "equipment_id": "EQ-2003"},
    {"name": "Mobile Command Vehicle", "type": "Vehicle - Command", "serial_number": "MCV-001", "equipment_id": "EQ-2004"},
    {"name": "Portable Repeater 1", "type": "Communications", "serial_number": "RPT-001", "equipment_id": "EQ-2005"},
    {"name": "Portable Repeater 2", "type": "Communications", "serial_number": "RPT-002", "equipment_id": "EQ-2006"},
    {"name": "Satellite Phone 1", "type": "Communications", "serial_number": "SAT-001", "equipment_id": "EQ-2007"},
    {"name": "GPS Unit 7", "type": "Navigation", "serial_number": "GPS-007", "equipment_id": "EQ-2008"},
    {"name": "GPS Unit 8", "type": "Navigation", "serial_number": "GPS-008", "equipment_id": "EQ-2009"},
    {"name": "Trauma Kit B", "type": "Medical", "serial_number": "MED-B12", "equipment_id": "EQ-2010"},
    {"name": "Trauma Kit C", "type": "Medical", "serial_number": "MED-C07", "equipment_id": "EQ-2011"},
    {"name": "Rope Rescue Kit 1", "type": "Technical Rescue", "serial_number": "RRK-001", "equipment_id": "EQ-2012"},
    {"name": "DJI Thermal Drone 2", "type": "sUAS", "serial_number": "UAS-002", "equipment_id": "EQ-2013"},
    {"name": "DJI Thermal Drone 3", "type": "sUAS", "serial_number": "UAS-003", "equipment_id": "EQ-2014"},
]

# ---------------------------------------------------------------------------
# Operational periods
# ---------------------------------------------------------------------------

OPERATIONAL_PERIODS = [
    {"key": "op1", "number": 1, "name": "Day 1 - Initial Search", "status": "Complete",
     "start": 0, "end": 720, "briefing": 0,
     "objectives": "Locate both overdue hikers (Alex Rivera and Jordan Pike); prioritize high-probability areas before nightfall.",
     "weather_summary": "Clear, 55F, winds 5-10mph.",
     "safety_message": "Watch for loose rock on ravine trails; hydrate frequently; buddy system at all times."},
    {"key": "op2", "number": 2, "name": "Night 1 - Continued Search (Overnight)", "status": "Complete",
     "start": 720, "end": 1440, "briefing": 720,
     "objectives": "Continue search for second missing hiker (Jordan Pike) using night vision and thermal imaging assets.",
     "weather_summary": "Clear, 40F overnight, calm winds.",
     "safety_message": "Night operations: radio check-in every 15 minutes, chem-lights for team marking, watch for drop-offs."},
]

# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

TEAMS = [
    {"key": "alpha", "name": "Ground Team Alpha", "callsign": "Alpha", "team_leader": "Grace Lindqvist",
     "leader_phone": "555-0105", "team_type": "Ground", "role": "Search",
     "members": ["Grace Lindqvist", "Omar Delacroix"]},
    {"key": "bravo", "name": "Ground Team Bravo", "callsign": "Bravo", "team_leader": "Yuki Tanabe",
     "leader_phone": "555-0107", "team_type": "Ground", "role": "Search",
     "members": ["Yuki Tanabe", "Lena Brodský"]},
    {"key": "charlie", "name": "Ground Team Charlie", "callsign": "Charlie", "team_leader": "Victor Kowalczyk",
     "leader_phone": "555-0116", "team_type": "Ground", "role": "Search",
     "members": ["Victor Kowalczyk", "Ines Albrecht"]},
    {"key": "delta", "name": "Ground Team Delta", "callsign": "Delta", "team_leader": "Desmond Okafor",
     "leader_phone": "555-0118", "team_type": "Ground", "role": "Search",
     "members": ["Desmond Okafor", "Hannah Vuković"]},
    {"key": "k9_1", "name": "K9 Team 1", "callsign": "K9-1", "team_leader": "Caleb Ferreira",
     "leader_phone": "555-0109", "team_type": "K9", "role": "Search",
     "members": ["Caleb Ferreira"]},
    {"key": "k9_2", "name": "K9 Team 2", "callsign": "K9-2", "team_leader": "Marisol Quintana",
     "leader_phone": "555-0120", "team_type": "K9", "role": "Search",
     "members": ["Marisol Quintana"]},
    {"key": "drone1", "name": "Drone Team 1", "callsign": "Air 1", "team_leader": "Noelle Ashworth",
     "leader_phone": "555-0110", "team_type": "AIR", "role": "Reconnaissance",
     "members": ["Noelle Ashworth"]},
    {"key": "drone2", "name": "Drone Team 2", "callsign": "Air 2", "team_leader": "Trevor Lindgren",
     "leader_phone": "555-0121", "team_type": "AIR", "role": "Reconnaissance",
     "members": ["Trevor Lindgren"]},
]

# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

TASKS = [
    {"key": "T1", "op": "op1", "title": "Search Eagle Ridge Trailhead to Overlook", "category": "Search",
     "task_type": "Ground Search", "priority": "High", "location": "Eagle Ridge Trailhead",
     "status": "Completed",
     "assignment": "Sweep the primary trail corridor from the trailhead to the overlook, flagging any sign."},
    {"key": "T2", "op": "op1", "title": "Search Lower Creek Drainage", "category": "Search",
     "task_type": "Ground Search", "priority": "High", "location": "Lower Creek Drainage",
     "status": "Completed",
     "assignment": "Grid search the creek drainage below the trailhead; high probability area."},
    {"key": "T3", "op": "op1", "title": "K9 Scent Search Grid 3", "category": "Search",
     "task_type": "K9 Search", "priority": "Medium", "location": "Grid 3 - North Slope",
     "status": "Completed",
     "assignment": "Air-scent search of Grid 3 starting from the subjects' last known point."},
    {"key": "T4", "op": "op1", "title": "Aerial Thermal Sweep Sector 4", "category": "Search",
     "task_type": "Aerial Search", "priority": "Medium", "location": "Sector 4 - Ridge Face",
     "status": "Completed",
     "assignment": "Thermal drone sweep of the ridge face, too steep for ground teams."},
    {"key": "T5", "op": "op1", "title": "Base Camp / ICP Setup", "category": "Logistics",
     "task_type": "Support", "priority": "Low", "location": "Eagle Ridge Trailhead Parking Lot",
     "status": "Completed",
     "assignment": "Establish ICP, staging, and communications repeater."},
    {"key": "T6", "op": "op1", "title": "Search Northern Ravine Trail", "category": "Search",
     "task_type": "Ground Search", "priority": "Medium", "location": "Northern Ravine Trail",
     "status": "Completed",
     "assignment": "Sweep the Northern Ravine Trail to the first switchback junction and overlook."},
    {"key": "T7", "op": "op2", "title": "Night Search Grid 5 (NVG)", "category": "Search",
     "task_type": "Ground Search", "priority": "High", "location": "Grid 5 - Southern Brush Line",
     "status": "Completed",
     "assignment": "Night-vision-equipped ground sweep of Grid 5 for second missing hiker."},
    {"key": "T8", "op": "op2", "title": "K9 Overnight Scent Sweep Grid 6", "category": "Search",
     "task_type": "K9 Search", "priority": "High", "location": "Grid 6 - North Slope Extension",
     "status": "Completed",
     "assignment": "Overnight air-scent search of Grid 6."},
    {"key": "T9", "op": "op2", "title": "Thermal Drone Overnight Sweep Sector 7", "category": "Search",
     "task_type": "Aerial Search", "priority": "High", "location": "Sector 7 - Rock Outcropping",
     "status": "Completed",
     "assignment": "Overnight thermal drone sweep of Sector 7."},
    {"key": "T10", "op": "op2", "title": "Subject Recovery and Medical Evacuation", "category": "Medical",
     "task_type": "Evacuation", "priority": "High", "location": "Sector 7 - Rock Outcropping",
     "status": "Completed",
     "assignment": "Assess and evacuate recovered subject(s) to ICP for EMS handoff."},
]

TASK_TEAM = [
    ("T1", "alpha", True),
    ("T2", "bravo", True),
    ("T3", "k9_1", True),
    ("T4", "drone1", True),
    ("T6", "charlie", True),
    ("T7", "delta", True),
    ("T8", "k9_2", True),
    ("T9", "drone2", True),
]

# ---------------------------------------------------------------------------
# Task narrative / log entries: (minutes from START_TIME, task_key, team_key, author, text, critical)
# ---------------------------------------------------------------------------

NARRATIVE = [
    (0, "T5", None, "Hector Villarreal", "ICP established at trailhead parking lot. Repeater 1 on channel SAR-TAC1.", False),
    (5, "T5", None, "Dana Whitfield", "0600 operational briefing complete. OP1 objectives: clear high-probability areas in Divisions A-C before nightfall for two overdue hikers, Alex Rivera and Jordan Pike.", False),
    (10, "T1", "alpha", "Grace Lindqvist", "Alpha team departing trailhead, beginning sweep toward overlook.", False),
    (12, "T2", "bravo", "Yuki Tanabe", "Bravo team entering creek drainage, grid search underway.", False),
    (15, "T3", "k9_1", "Caleb Ferreira", "K9-1 on scene at Grid 3, beginning air-scent search.", False),
    (18, "T4", "drone1", "Noelle Ashworth", "Drone airborne, starting thermal sweep of Sector 4.", False),
    (20, "T6", "charlie", "Victor Kowalczyk", "Charlie team departing ICP toward Northern Ravine Trail.", False),
    (35, "T6", "charlie", "Ines Albrecht", "Charlie team reports loose rock hazard on ravine trail switchbacks, proceeding with caution.", False),
    (45, "T1", "alpha", "Omar Delacroix", "Alpha 2 twisted ankle on rocky section, self-treated, continuing mission.", False),
    (55, "T1", "alpha", "Grace Lindqvist", "Alpha team at overlook, no sign found. Holding position, awaiting instructions.", False),
    (60, "T4", "drone1", "Noelle Ashworth", "Battery swap complete, resuming thermal sweep of Sector 4 northern half.", False),
    (70, "T2", "bravo", "Lena Brodský", "Bravo team located a blue backpack matching Alex Rivera's description near creek bend.", True),
    (72, "T2", "bravo", "Yuki Tanabe", "Backpack secured as evidence, GPS marked. Requesting K9 team redirect to this location.", True),
    (75, "T5", None, "Marcus Oyelaran", "Ops directing K9-1 to creek bend coordinates per Bravo's find. Charlie to continue ravine sweep.", False),
    (80, "T3", "k9_1", "Caleb Ferreira", "K9-1 redirected to creek bend per Ops. En route.", False),
    (90, "T6", "charlie", "Victor Kowalczyk", "Charlie team cleared Northern Ravine Trail to the first switchback junction, no sign.", False),
    (95, "T4", "drone1", "Noelle Ashworth", "Thermal sweep of Sector 4 complete, no anomalies detected. Returning to base.", False),
    (100, "T5", None, "Hector Villarreal", "Weather check: wind increasing to 15mph, temperature dropping. Monitoring conditions ahead of possible OP2 night search.", False),
    (110, "T3", "k9_1", "Caleb Ferreira", "K9-1 alerting strongly on scent trail heading upslope from backpack location.", True),
    (120, "T6", "charlie", "Ines Albrecht", "Charlie team reached ravine overlook, no sign, requesting permission to return to ICP.", False),
    (125, "T5", None, "Marcus Oyelaran", "Charlie team released, returning to ICP for reassignment or stand-down.", False),
    (130, "T3", "k9_1", "Caleb Ferreira", "Subject located, conscious and alert, minor exposure injuries. Identified as Alex Rivera. Requesting medic.", True),
    (132, "T5", None, "Dana Whitfield", "Alex Rivera located near creek bend upslope area. Second subject Jordan Pike still unaccounted for; continuing search.", True),
    (135, "T2", "bravo", "Omar Delacroix", "Medic Omar Delacroix en route to Rivera's location to assist K9 team.", True),
    (150, "T3", "k9_1", "Caleb Ferreira", "Rivera assessed by medic, ambulatory with assistance. Beginning litter-assisted evacuation to trailhead.", False),
    (160, "T1", "alpha", "Grace Lindqvist", "Alpha team meeting evacuation party at overlook junction to assist carryout.", False),
    (170, "T5", None, "Aisha Rahman", "Rivera's vitals stable, mild hypothermia and dehydration. Continuing evac to ICP for EMS handoff.", False),
    (180, "T5", None, "Dana Whitfield", "Alex Rivera arrived at ICP, transferred to EMS for transport. One of two subjects recovered.", False),
    (185, "T5", None, "Priya Narayanan", "Confirmed Rivera's identity matches missing person report. Family notified; Rivera en route to hospital.", False),
    (195, "T5", None, "Renata Souza", "Logistics resupplying water, batteries, and trauma kits at ICP ahead of continued operations for Jordan Pike.", False),
    (210, "T5", None, "Dana Whitfield", "No sign of Jordan Pike during OP1 daylight hours. Planning night operations; OP2 briefing scheduled 1800.", False),
    (300, "T5", None, "Sumiko Kagawa", "Comms check across all channels, Repeater 1 and Repeater 2 both nominal. Satellite phone on standby for dead zones.", False),
    (400, "T5", None, "Hector Villarreal", "Midday safety brief: heat index rising, mandatory water breaks every 30 minutes for remaining field teams.", False),
    (480, "T5", None, "Walter Begay", "County Sheriff's Office liaison confirms additional mutual-aid K9 unit available if Pike is not located by dusk.", False),
    (600, "T5", None, "Abigail Stroud", "Press briefing held at ICP perimeter; confirmed one subject recovered, search continuing for second hiker.", False),
    (700, "T5", None, "Dana Whitfield", "OP1 closing out. All daylight teams to ICP for debrief and reassignment ahead of OP2 night briefing.", False),
    (720, "T5", None, "Dana Whitfield", "1800 shift change briefing. OP2 objective: continue search for Jordan Pike, last associated with Grid 5. Night operations authorized with NVG-equipped team.", False),
    (725, "T5", None, "Renata Souza", "Logistics confirms night search equipment issued: NVGs, chem lights, extra batteries for all OP2 teams.", False),
    (730, "T7", "delta", "Desmond Okafor", "Delta team departing ICP for Grid 5 night search.", False),
    (735, "T8", "k9_2", "Marisol Quintana", "K9-2 beginning overnight scent sweep of Grid 6.", False),
    (740, "T9", "drone2", "Trevor Lindgren", "Night thermal drone airborne for Sector 7 overnight sweep.", False),
    (760, "T7", "delta", "Hannah Vuković", "Delta team reports dense brush slowing progress in Grid 5 southern section.", False),
    (800, "T9", "drone2", "Trevor Lindgren", "Thermal anomaly detected in Sector 7, possible heat signature near rock outcropping. Ground team requested.", True),
    (805, "T5", None, "Marcus Oyelaran", "Redirecting Delta team to investigate thermal anomaly in Sector 7 per drone report.", False),
    (820, "T7", "delta", "Desmond Okafor", "Delta team approaching anomaly location, visual contact with a person.", True),
    (825, "T7", "delta", "Desmond Okafor", "Subject identified as Jordan Pike, conscious but hypothermic. Requesting medic and litter.", True),
    (830, "T10", None, "Aisha Rahman", "Medical team dispatched to Sector 7 for second subject evacuation.", True),
    (850, "T8", "k9_2", "Marisol Quintana", "K9-2 confirms scent trail matches Pike's recovery location, standing down overnight sweep of Grid 6.", False),
    (870, "T10", None, "Aisha Rahman", "Pike assessed: moderate hypothermia, stable vitals. Beginning evacuation to ICP.", False),
    (900, "T10", None, "Aisha Rahman", "Evacuation party clear of rough terrain, ETA to ICP 30 minutes.", False),
    (910, "T9", "drone2", "Trevor Lindgren", "Overnight thermal sweep of Sector 7 complete, no further anomalies. Drone returning to base.", False),
    (930, "T5", None, "Dana Whitfield", "Jordan Pike arrived at ICP, transferred to EMS for transport. Both subjects recovered.", False),
    (935, "T5", None, "Priya Narayanan", "All search objectives met. Beginning demobilization planning for OP3 stand-down.", False),
    (940, "T5", None, "Hector Villarreal", "No injuries to personnel during OP2 night operations. Closing safety log for this incident.", False),
    (945, "T5", None, "Felix Ndiaye", "Finance/Admin logging personnel hours and equipment usage for OP1 and OP2 for after-action cost summary.", False),
]

# ---------------------------------------------------------------------------
# Work assignments (ICS-204 style), linked to tasks
# ---------------------------------------------------------------------------

WORK_ASSIGNMENTS = [
    {"name": "Division A - Trail Corridor Ground Search", "op": "op1", "branch": "Ground Branch", "division_group": "Division A",
     "assignment_kind": "Ground", "priority": "High",
     "description": "Primary trail corridor search from trailhead to overlook.",
     "tactics_summary": "Linear sweep with 2-person team, visual and audio contact every 50m.",
     "task_keys": ["T1"]},
    {"name": "Division B - Creek Drainage Ground Search", "op": "op1", "branch": "Ground Branch", "division_group": "Division B",
     "assignment_kind": "Ground", "priority": "High",
     "description": "High-probability creek drainage search.",
     "tactics_summary": "Grid search, 15m spacing, flag all sign for K9 follow-up.",
     "task_keys": ["T2", "T3"]},
    {"name": "Division C - Northern Ravine Ground Search", "op": "op1", "branch": "Ground Branch", "division_group": "Division C",
     "assignment_kind": "Ground", "priority": "Medium",
     "description": "Secondary ravine trail search, lower probability area.",
     "tactics_summary": "Linear sweep to first switchback junction and overlook, monitor for loose rock hazard.",
     "task_keys": ["T6"]},
    {"name": "Air Ops - Daytime Aerial Reconnaissance", "op": "op1", "branch": "Air Operations Branch", "division_group": "",
     "assignment_kind": "Air", "priority": "Medium",
     "description": "Thermal drone sweep of terrain inaccessible to ground teams.",
     "tactics_summary": "Grid flight pattern at 200ft AGL with thermal camera.",
     "task_keys": ["T4"]},
    {"name": "Division D - Night Search Grid 5/6", "op": "op2", "branch": "Night Operations Branch", "division_group": "Division D",
     "assignment_kind": "Ground", "priority": "High",
     "description": "Overnight NVG ground sweep and K9 scent search for second missing hiker.",
     "tactics_summary": "Paired ground/K9 sweep with 15-minute radio check-ins and chem-light team marking.",
     "task_keys": ["T7", "T8"]},
    {"name": "Air Ops - Night Thermal Reconnaissance", "op": "op2", "branch": "Air Operations Branch", "division_group": "",
     "assignment_kind": "Air", "priority": "High",
     "description": "Overnight thermal drone sweep of Sector 7.",
     "tactics_summary": "Grid flight pattern at 200ft AGL, report any thermal anomaly immediately to Ops.",
     "task_keys": ["T9"]},
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://localhost:8765", help="Base URL of a running sarapp_db server")
    parser.add_argument("--number", default=None, help="Incident number (default: DEMO-<timestamp>, to avoid collisions)")
    parser.add_argument("--name", default="Eagle Ridge Missing Hikers (Demo)", help="Incident name")
    args = parser.parse_args()

    number = args.number or f"DEMO-{datetime.now():%Y%m%d-%H%M%S}"
    client = httpx.Client(base_url=args.base_url.rstrip("/"), timeout=30.0)

    def post(path: str, json: dict) -> dict:
        resp = client.post(path, json=json)
        resp.raise_for_status()
        return resp.json()

    def put(path: str, json: dict) -> dict:
        resp = client.put(path, json=json)
        resp.raise_for_status()
        return resp.json()

    def patch(path: str, json: dict) -> dict:
        resp = client.patch(path, json=json)
        resp.raise_for_status()
        return resp.json()

    def get_or_create_person(p: dict) -> int:
        existing = client.get("/api/master/personnel", params={"search": p["person_id"]}).json()
        match = next((d for d in existing if d.get("person_id") == p["person_id"]), None)
        if match:
            return match["person_record"]
        return post("/api/master/personnel", p)["person_record"]

    def get_or_create_equipment(e: dict) -> int:
        existing = client.get("/api/master/equipment", params={"search": e["equipment_id"]}).json()
        match = next((d for d in existing if d.get("equipment_id") == e["equipment_id"]), None)
        if match:
            return match["equipment_record"]
        return post("/api/master/equipment", e)["equipment_record"]

    print(f"Connecting to {args.base_url} ...")
    try:
        client.get("/docs")
    except httpx.HTTPError as exc:
        print(f"Could not reach server at {args.base_url}: {exc}", file=sys.stderr)
        return 1

    print(f"Creating/reusing {len(PERSONNEL)} master catalog personnel...")
    person_records: dict[str, int] = {p["name"]: get_or_create_person(p) for p in PERSONNEL}

    print(f"Creating/reusing {len(EQUIPMENT)} master catalog equipment items...")
    equipment_records: dict[str, int] = {e["name"]: get_or_create_equipment(e) for e in EQUIPMENT}

    print(f"Creating incident {number!r}...")
    incident = post("/api/incidents", {
        "number": number,
        "name": args.name,
        "type": "Search and Rescue - Lost Person",
        "description": (
            "Two overdue hikers, Alex Rivera and Jordan Pike, last seen together near the Eagle Ridge "
            "Trailhead before becoming separated. Search initiated after family report; operation spans "
            "two operational periods including an overnight search for the second subject."
        ),
        "icp_location": "Eagle Ridge Trailhead Parking Lot",
        "is_training": True,
    })
    incident_id = incident["id"]

    print("Creating operational periods...")
    op_ids: dict[str, int] = {}
    for op in OPERATIONAL_PERIODS:
        doc = post(f"/api/incidents/{incident_id}/planning/operational-periods", {
            "number": op["number"],
            "name": op["name"],
            "status": op["status"],
            "start_time": at(op["start"]),
            "end_time": at(op["end"]),
            "briefing_time": at(op["briefing"]),
            "objectives": op["objectives"],
            "weather_summary": op["weather_summary"],
            "safety_message": op["safety_message"],
        })
        op_ids[op["key"]] = doc["id"]

    print("Checking in personnel...")
    for name, record in person_records.items():
        put(f"/api/incidents/{incident_id}/checkin/{record}", {
            "status": "Checked In",
            "arrival_time": at(0),
            "changed_by": "Demo Generator",
        })

    print("Checking in equipment...")
    for name, record in equipment_records.items():
        post(f"/api/incidents/{incident_id}/resources/equipment/{record}", {
            "status": "Checked In",
            "changed_by": "Demo Generator",
        })

    print(f"Creating {len(TEAMS)} teams...")
    team_ids: dict[str, int] = {}
    for t in TEAMS:
        doc = post(f"/api/incidents/{incident_id}/operations/teams", {
            "name": t["name"],
            "callsign": t["callsign"],
            "team_leader": t["team_leader"],
            "leader_phone": t["leader_phone"],
            "team_type": t["team_type"],
            "role": t["role"],
            "member_person_records": [person_records[n] for n in t["members"]],
        })
        team_ids[t["key"]] = doc["int_id"]

    print(f"Creating {len(TASKS)} tasks...")
    task_ids: dict[str, int] = {}
    for t in TASKS:
        doc = post(f"/api/incidents/{incident_id}/operations/tasks", {
            "title": t["title"],
            "category": t["category"],
            "task_type": t["task_type"],
            "priority": t["priority"],
            "status": t["status"],
            "location": t["location"],
            "assignment": t["assignment"],
            "created_by": "Priya Narayanan",
        })
        task_id = doc["int_id"]
        task_ids[t["key"]] = task_id
        patch(f"/api/incidents/{incident_id}/operations/tasks/{task_id}", {
            "operational_period_id": op_ids[t["op"]],
        })

    print("Assigning teams to tasks...")
    for task_key, team_key, primary in TASK_TEAM:
        post(f"/api/incidents/{incident_id}/operations/tasks/{task_ids[task_key]}/teams", {
            "team_id": team_ids[team_key],
            "primary": primary,
        })

    print(f"Writing {len(NARRATIVE)} task narrative entries...")
    for minutes, task_key, team_key, by_name, text, critical in NARRATIVE:
        post(f"/api/incidents/{incident_id}/narratives", {
            "task_id": task_ids[task_key],
            "timestamp": at(minutes),
            "narrative": text,
            "entered_by": str(person_records[by_name]),
            "team_num": str(team_ids[team_key]) if team_key else "",
            "critical": 1 if critical else 0,
        })

    print(f"Creating {len(WORK_ASSIGNMENTS)} work assignments and linking tasks...")
    for wa in WORK_ASSIGNMENTS:
        doc = post(f"/api/incidents/{incident_id}/planning/work-assignments", {
            "assignment_name": wa["name"],
            "operational_period_id": op_ids[wa["op"]],
            "branch": wa["branch"],
            "division_group": wa["division_group"],
            "assignment_kind": wa["assignment_kind"],
            "priority": wa["priority"],
            "planning_status": "Approved",
            "description": wa["description"],
            "tactics_summary": wa["tactics_summary"],
            "prepared_by": "Priya Narayanan",
            "approved_by": "Dana Whitfield",
        })
        wa_id = doc["id"]
        for task_key in wa["task_keys"]:
            post(f"/api/incidents/{incident_id}/planning/work-assignments/{wa_id}/task-links", {
                "task_id": task_ids[task_key],
            })

    print()
    print(f"Done. Demo incident {args.name!r} created (number={number}, id={incident_id}).")
    print(f"  Personnel: {len(person_records)}  Equipment: {len(equipment_records)}  Teams: {len(team_ids)}")
    print(f"  Tasks: {len(task_ids)}  Narrative entries: {len(NARRATIVE)}  Work assignments: {len(WORK_ASSIGNMENTS)}")
    print(f"  Operational periods: {len(op_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
