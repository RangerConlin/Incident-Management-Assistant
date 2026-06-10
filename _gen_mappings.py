"""
Generate / update mapping.json files for all forms in forms/catalog.json.

Existing mappings that are already correct (ics_205, ics_213, ics_214) are
left untouched.  All others are written (or rewritten if they were scaffolds).
"""

import json
from pathlib import Path

SETS_ROOT = Path(__file__).parent / "forms" / "sets" / "fema"


def write(form_id: str, description: str, fields: list[dict]) -> None:
    dest = SETS_ROOT / form_id
    dest.mkdir(parents=True, exist_ok=True)
    mapping = {"description": description, "fields": fields}
    (dest / "mapping.json").write_text(
        json.dumps(mapping, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  wrote {form_id}/mapping.json  ({len(fields)} fields)")


def s(key: str, default: str = "") -> dict:
    """Simple source dict with optional default."""
    return {"key": key, "default": default}


def date(key: str) -> dict:
    return {"key": key, "transform": "date_short", "default": ""}


def time_(key: str) -> dict:
    return {"key": key, "transform": "time_short", "default": ""}


def dt(key: str) -> dict:
    return {"key": key, "transform": "datetime_short", "default": ""}


def lit(value: str) -> dict:
    return {"literal": value}


# ---------------------------------------------------------------------------
# Common header blocks
# ---------------------------------------------------------------------------

def incident_header(name_field="IncidentName", number_field="IncidentNumber") -> list[dict]:
    return [
        {"pdf_field": name_field,   "source": "incident.name"},
        {"pdf_field": number_field, "source": s("incident.number")},
    ]


def op_period_block(
    date_from="OpPeriodDateFrom", time_from="OpPeriodTimeFrom",
    date_to="OpPeriodDateTo",   time_to="OpPeriodTimeTo",
) -> list[dict]:
    return [
        {"pdf_field": date_from, "source": date("op_period.start")},
        {"pdf_field": time_from, "source": time_("op_period.start")},
        {"pdf_field": date_to,   "source": date("op_period.end")},
        {"pdf_field": time_to,   "source": time_("op_period.end")},
    ]


def prepared_by_block(
    name_field="PreparedByName", position_field="PreparedByPosition",
    dt_field="PreparedDateTime",
) -> list[dict]:
    return [
        {"pdf_field": name_field,     "source": "prepared_by.name"},
        {"pdf_field": position_field, "source": "prepared_by.position"},
        {"pdf_field": dt_field,       "source": dt("prepared_by.date_time")},
    ]


# ---------------------------------------------------------------------------
# ICS 201 — Incident Briefing
# ---------------------------------------------------------------------------
def gen_ics_201():
    fields = [
        {"pdf_field": "IncidentName",       "source": "incident.name"},
        {"pdf_field": "IncidentNumber",     "source": s("incident.number")},
        {"pdf_field": "DateTimePrepared",   "source": dt("prepared_by.date_time")},
        {"pdf_field": "MapReference",       "source": s("incident.icp_location")},
        {"pdf_field": "ICPLocation",        "source": s("incident.icp_location")},
        {"pdf_field": "SituationSummary",   "source": s("incident.description")},
        # Objectives rows 1-8
        *[{"pdf_field": f"Objective{i+1}", "source": s(f"objectives.{i}.text")} for i in range(8)],
        # Current organization
        {"pdf_field": "IncidentCommander",  "source": s("organization.incident_commander.name")},
        {"pdf_field": "OperationsChief",    "source": s("organization.operations_section_chief.name")},
        {"pdf_field": "PlanningChief",      "source": s("organization.planning_section_chief.name")},
        {"pdf_field": "LogisticsChief",     "source": s("organization.logistics_section_chief.name")},
        # Resources summary rows 1-8
        *[{"pdf_field": f"ResourceName{i+1}",   "source": s(f"teams.{i}.name")}   for i in range(8)],
        *[{"pdf_field": f"ResourceStatus{i+1}", "source": s(f"teams.{i}.status")} for i in range(8)],
        *[{"pdf_field": f"ResourceLeader{i+1}", "source": s(f"teams.{i}.leader_name")} for i in range(8)],
        # Prepared by
        {"pdf_field": "PreparedByName",     "source": "prepared_by.name"},
        {"pdf_field": "PreparedByPosition", "source": "prepared_by.position"},
        {"pdf_field": "PreparedDateTime",   "source": dt("prepared_by.date_time")},
    ]
    write("ics_201", "ICS 201 Incident Briefing — FEMA", fields)


# ---------------------------------------------------------------------------
# ICS 202 — Incident Objectives
# ---------------------------------------------------------------------------
def gen_ics_202():
    fields = [
        {"pdf_field": "IncidentName",     "source": "incident.name"},
        {"pdf_field": "IncidentNumber",   "source": s("incident.number")},
        *op_period_block(),
        {"pdf_field": "CommandEmphasis",  "source": s("incident.description")},
        # Objectives
        *[{"pdf_field": f"Objective{i+1}", "source": s(f"objectives.{i}.text")} for i in range(8)],
        # Attachments checklist — leave as literal (user fills)
        {"pdf_field": "WeatherForecast",  "source": s("incident.description", "")},
        # Prepared by
        {"pdf_field": "PreparedByName",     "source": "prepared_by.name"},
        {"pdf_field": "PreparedByPosition", "source": "prepared_by.position"},
        {"pdf_field": "PreparedDateTime",   "source": dt("prepared_by.date_time")},
        {"pdf_field": "ICApprovedBy",       "source": s("organization.incident_commander.name")},
    ]
    write("ics_202", "ICS 202 Incident Objectives — FEMA", fields)


# ---------------------------------------------------------------------------
# ICS 203 — Organization Assignment List  (FIX: wrong org key names)
# ---------------------------------------------------------------------------
def gen_ics_203():
    fields = [
        {"pdf_field": "IncidentName",           "source": "incident.name"},
        {"pdf_field": "IncidentNumber",         "source": s("incident.number")},
        {"pdf_field": "OpPeriodFrom",           "source": date("op_period.start")},
        {"pdf_field": "OpPeriodTo",             "source": date("op_period.end")},
        {"pdf_field": "OpPeriodFromTime",       "source": time_("op_period.start")},
        {"pdf_field": "OpPeriodToTime",         "source": time_("op_period.end")},
        # Command Staff
        {"pdf_field": "IncidentCommander",      "source": s("organization.incident_commander.name")},
        {"pdf_field": "DeputyIC",               "source": s("organization.deputy_incident_commander.name")},
        {"pdf_field": "SafetyOfficer",          "source": s("organization.safety_officer.name")},
        {"pdf_field": "LiaisonOfficer",         "source": s("organization.liaison_officer.name")},
        {"pdf_field": "PIOfficer",              "source": s("organization.public_information_officer.name")},
        # General Staff
        {"pdf_field": "OperationsChief",        "source": s("organization.operations_section_chief.name")},
        {"pdf_field": "PlanningChief",          "source": s("organization.planning_section_chief.name")},
        {"pdf_field": "LogisticsChief",         "source": s("organization.logistics_section_chief.name")},
        {"pdf_field": "FinanceChief",           "source": s("organization.finance_admin_section_chief.name")},
        # Unit leaders
        {"pdf_field": "SituationUnitLeader",    "source": s("organization.situation_unit_leader.name")},
        {"pdf_field": "ResourcesUnitLeader",    "source": s("organization.resources_unit_leader.name")},
        {"pdf_field": "DocumentationUnitLeader","source": s("organization.documentation_unit_leader.name")},
        {"pdf_field": "DemobUnitLeader",        "source": s("organization.demobilization_unit_leader.name")},
        {"pdf_field": "CommsUnitLeader",        "source": s("organization.communications_unit_leader.name")},
        {"pdf_field": "MedicalUnitLeader",      "source": s("organization.medical_unit_leader.name")},
        {"pdf_field": "GroundSupportUnitLeader","source": s("organization.ground_support_unit_leader.name")},
        {"pdf_field": "FacilitiesUnitLeader",   "source": s("organization.facilities_unit_leader.name")},
        {"pdf_field": "SupplyUnitLeader",       "source": s("organization.supply_unit_leader.name")},
        {"pdf_field": "FoodUnitLeader",         "source": s("organization.food_unit_leader.name")},
        {"pdf_field": "AirOpsBranchDirector",   "source": s("organization.air_operations_branch_director.name")},
        {"pdf_field": "StagingAreaManager",     "source": s("organization.staging_area_manager.name")},
        # Prepared by
        {"pdf_field": "PreparedBy",             "source": "prepared_by.name"},
        {"pdf_field": "PreparedDateTime",       "source": dt("prepared_by.date_time")},
    ]
    write("ics_203", "ICS 203 Organization Assignment List — FEMA", fields)


# ---------------------------------------------------------------------------
# ICS 204 — Assignment List  (FIX: align field names to context.py columns)
# ---------------------------------------------------------------------------
def gen_ics_204():
    fields = [
        {"pdf_field": "IncidentName",        "source": "incident.name"},
        {"pdf_field": "IncidentNumber",      "source": s("incident.number")},
        *op_period_block(),
        {"pdf_field": "BranchDivGroup",      "source": s("tasks.0.assignment")},
        {"pdf_field": "StagingArea",         "source": s("tasks.0.location")},
        {"pdf_field": "OperationsChief",     "source": s("organization.operations_section_chief.name")},
        # Resources / teams
        *[{"pdf_field": f"ResourceName{i+1}",   "source": s(f"teams.{i}.name")}        for i in range(5)],
        *[{"pdf_field": f"Leader{i+1}",          "source": s(f"teams.{i}.leader_name")} for i in range(5)],
        *[{"pdf_field": f"ContactInfo{i+1}",     "source": s(f"teams.{i}.resource_type")} for i in range(5)],
        # Task details
        {"pdf_field": "WorkAssignment",      "source": s("tasks.0.assignment")},
        {"pdf_field": "SpecialInstructions", "source": s("tasks.0.title")},
        {"pdf_field": "Communications",      "source": s("tasks.0.radio_primary")},
        # Prepared by
        {"pdf_field": "PreparedBy",          "source": "prepared_by.name"},
        {"pdf_field": "PreparedDateTime",    "source": dt("prepared_by.date_time")},
    ]
    write("ics_204", "ICS 204 Assignment List — FEMA", fields)


# ---------------------------------------------------------------------------
# ICS 205 — Radio Communications Plan  (already correct, skip)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ICS 205A — Communications List
# ---------------------------------------------------------------------------
def gen_ics_205a():
    rows = []
    for i in range(8):
        rows += [
            {"pdf_field": f"NameRow{i+1}",           "source": s(f"agency_contacts.{i}.name")},
            {"pdf_field": f"ICSPositionRow{i+1}",    "source": s(f"agency_contacts.{i}.title")},
            {"pdf_field": f"HomeAgencyRow{i+1}",     "source": s(f"agency_contacts.{i}.agency")},
            {"pdf_field": f"OfficeRow{i+1}",         "source": s(f"agency_contacts.{i}.phone")},
            {"pdf_field": f"CellRow{i+1}",           "source": s(f"agency_contacts.{i}.phone")},
            {"pdf_field": f"OtherRow{i+1}",          "source": s(f"agency_contacts.{i}.email")},
        ]
    fields = [
        {"pdf_field": "IncidentName",    "source": "incident.name"},
        {"pdf_field": "IncidentNumber",  "source": s("incident.number")},
        *op_period_block(),
        *rows,
        {"pdf_field": "PreparedBy",      "source": "prepared_by.name"},
        {"pdf_field": "PreparedDateTime","source": dt("prepared_by.date_time")},
    ]
    write("ics_205a", "ICS 205A Communications List — FEMA", fields)


# ---------------------------------------------------------------------------
# ICS 206 — Medical Plan  (has PDF scaffold — map real data to known fields)
# ---------------------------------------------------------------------------
def gen_ics_206():
    fields = [
        {"pdf_field": "1 Incident Name_10",  "source": "incident.name"},
        {"pdf_field": "Date From",           "source": date("op_period.start")},
        {"pdf_field": "Date To",             "source": date("op_period.end")},
        {"pdf_field": "Time From",           "source": time_("op_period.start")},
        {"pdf_field": "Time To",             "source": time_("op_period.end")},
        # Medical Aid Stations (section 3)
        *[{"pdf_field": f"NameRow{i+1}",                        "source": s(f"ems_agencies.{i}.name")}         for i in range(5)],
        *[{"pdf_field": f"LocationRow{i+1}",                    "source": s(f"ems_agencies.{i}.address")}      for i in range(5)],
        *[{"pdf_field": f"Contact Numbers FrequencyRow{i+1}",   "source": s(f"ems_agencies.{i}.phone")}        for i in range(5)],
        # Ambulance transport (section 4)
        *[{"pdf_field": f"Ambulance ServiceRow{i+1}",           "source": s(f"ems_agencies.{i}.name")}         for i in range(4)],
        *[{"pdf_field": f"Contact NumbersFrequencyRow{i+1}",    "source": s(f"ems_agencies.{i}.phone")}        for i in range(4)],
        # Hospitals (section 5)
        *[{"pdf_field": f"Hospital NameRow{i+1}",               "source": s(f"hospitals.{i}.name")}            for i in range(5)],
        *[{"pdf_field": f"Address Latitude  Longitude if HelipadRow{i+1}", "source": s(f"hospitals.{i}.address")} for i in range(5)],
        *[{"pdf_field": f"AirRow{i+1}",                         "source": s(f"hospitals.{i}.phone")}           for i in range(5)],
        *[{"pdf_field": f"GroundRow{i+1}",                      "source": s(f"hospitals.{i}.fax")}             for i in range(5)],
        # Sign-offs
        {"pdf_field": "7 Prepared by Medical Unit Leader Name",  "source": s("organization.medical_unit_leader.name")},
        {"pdf_field": "8 Approved by Safety Officer Name",       "source": s("organization.safety_officer.name")},
        {"pdf_field": "DateTime_10",                             "source": dt("prepared_by.date_time")},
        {"pdf_field": "Special Medical Emergency Procedures",    "source": s("incident.description")},
    ]
    write("ics_206", "ICS 206 Medical Plan — FEMA", fields)


# ---------------------------------------------------------------------------
# ICS 207 — Incident Organization Chart
# ---------------------------------------------------------------------------
def gen_ics_207():
    positions = [
        ("IncidentCommander",          "incident_commander"),
        ("DeputyIC1",                  "deputy_incident_commander"),
        ("SafetyOfficer",              "safety_officer"),
        ("LiaisonOfficer",             "liaison_officer"),
        ("PublicInfoOfficer",          "public_information_officer"),
        ("OperationsChief",            "operations_section_chief"),
        ("PlanningChief",              "planning_section_chief"),
        ("LogisticsChief",             "logistics_section_chief"),
        ("FinanceChief",               "finance_admin_section_chief"),
        ("SituationUnitLeader",        "situation_unit_leader"),
        ("ResourcesUnitLeader",        "resources_unit_leader"),
        ("DocumentationUnitLeader",    "documentation_unit_leader"),
        ("DemobUnitLeader",            "demobilization_unit_leader"),
        ("CommsUnitLeader",            "communications_unit_leader"),
        ("MedicalUnitLeader",          "medical_unit_leader"),
        ("GroundSupportUnitLeader",    "ground_support_unit_leader"),
        ("FacilitiesUnitLeader",       "facilities_unit_leader"),
        ("SupplyUnitLeader",           "supply_unit_leader"),
        ("FoodUnitLeader",             "food_unit_leader"),
        ("AirOpsBranchDirector",       "air_operations_branch_director"),
        ("StagingAreaManager",         "staging_area_manager"),
    ]
    fields = [
        {"pdf_field": "IncidentName",    "source": "incident.name"},
        {"pdf_field": "IncidentNumber",  "source": s("incident.number")},
        *op_period_block(),
        *[{"pdf_field": pf, "source": s(f"organization.{key}.name")} for pf, key in positions],
        {"pdf_field": "PreparedBy",      "source": "prepared_by.name"},
        {"pdf_field": "PreparedDateTime","source": dt("prepared_by.date_time")},
    ]
    write("ics_207", "ICS 207 Incident Organization Chart — FEMA", fields)


# ---------------------------------------------------------------------------
# ICS 208 — Safety Message / Plan
# ---------------------------------------------------------------------------
def gen_ics_208():
    fields = [
        {"pdf_field": "IncidentName",       "source": "incident.name"},
        {"pdf_field": "IncidentNumber",     "source": s("incident.number")},
        *op_period_block(),
        {"pdf_field": "SafetyMessage",      "source": s("incident.description")},
        *[{"pdf_field": f"SiteHazard{i+1}", "source": s(f"objectives.{i}.text")} for i in range(5)],
        {"pdf_field": "PreparedByName",     "source": s("organization.safety_officer.name")},
        {"pdf_field": "PreparedDateTime",   "source": dt("prepared_by.date_time")},
    ]
    write("ics_208", "ICS 208 Safety Message / Plan — FEMA", fields)


# ---------------------------------------------------------------------------
# ICS 209 — Incident Status Summary
# ---------------------------------------------------------------------------
def gen_ics_209():
    fields = [
        {"pdf_field": "IncidentName",       "source": "incident.name"},
        {"pdf_field": "IncidentNumber",     "source": s("incident.number")},
        {"pdf_field": "IncidentType",       "source": s("incident.type")},
        {"pdf_field": "ICPLocation",        "source": s("incident.icp_location")},
        {"pdf_field": "IncidentStartDate",  "source": date("incident.start_time")},
        {"pdf_field": "IncidentStartTime",  "source": time_("incident.start_time")},
        *op_period_block(),
        {"pdf_field": "IncidentDescription","source": s("incident.description")},
        {"pdf_field": "IncidentCommander",  "source": s("organization.incident_commander.name")},
        {"pdf_field": "OperationsChief",    "source": s("organization.operations_section_chief.name")},
        # Resources committed
        *[{"pdf_field": f"ResourceName{i+1}",   "source": s(f"teams.{i}.name")}        for i in range(8)],
        *[{"pdf_field": f"ResourceStatus{i+1}", "source": s(f"teams.{i}.status")}      for i in range(8)],
        {"pdf_field": "PreparedByName",     "source": "prepared_by.name"},
        {"pdf_field": "PreparedByPosition", "source": "prepared_by.position"},
        {"pdf_field": "PreparedDateTime",   "source": dt("prepared_by.date_time")},
    ]
    write("ics_209", "ICS 209 Incident Status Summary — FEMA", fields)


# ---------------------------------------------------------------------------
# ICS 210 — Resource Status Change
# ---------------------------------------------------------------------------
def gen_ics_210():
    rows = []
    for i in range(12):
        rows += [
            {"pdf_field": f"ResourceName{i+1}",     "source": s(f"teams.{i}.name")},
            {"pdf_field": f"ResourceType{i+1}",     "source": s(f"teams.{i}.resource_type")},
            {"pdf_field": f"ResourceStatus{i+1}",   "source": s(f"teams.{i}.status")},
            {"pdf_field": f"ResourceLeader{i+1}",   "source": s(f"teams.{i}.leader_name")},
        ]
    fields = [
        {"pdf_field": "IncidentName",    "source": "incident.name"},
        {"pdf_field": "IncidentNumber",  "source": s("incident.number")},
        *op_period_block(),
        *rows,
        {"pdf_field": "PreparedBy",      "source": "prepared_by.name"},
        {"pdf_field": "PreparedDateTime","source": dt("prepared_by.date_time")},
    ]
    write("ics_210", "ICS 210 Resource Status Change — FEMA", fields)


# ---------------------------------------------------------------------------
# ICS 211 — Incident Check-In List
# ---------------------------------------------------------------------------
def gen_ics_211():
    rows = []
    for i in range(20):
        rows += [
            {"pdf_field": f"Name{i+1}",         "source": s(f"personnel.{i}.name")},
            {"pdf_field": f"Agency{i+1}",        "source": s(f"personnel.{i}.agency")},
            {"pdf_field": f"RadioID{i+1}",       "source": s(f"personnel.{i}.radio_id")},
        ]
    fields = [
        {"pdf_field": "IncidentName",    "source": "incident.name"},
        {"pdf_field": "IncidentNumber",  "source": s("incident.number")},
        {"pdf_field": "CheckInDateTime", "source": dt("prepared_by.date_time")},
        {"pdf_field": "CheckInLocation", "source": s("incident.icp_location")},
        *rows,
        {"pdf_field": "PreparedBy",      "source": "prepared_by.name"},
        {"pdf_field": "PreparedDateTime","source": dt("prepared_by.date_time")},
    ]
    write("ics_211", "ICS 211 Incident Check-In List — FEMA", fields)


# ---------------------------------------------------------------------------
# ICS 213 — General Message  (already correct, skip)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ICS 213RR — Resource Request Message
# ---------------------------------------------------------------------------
def gen_ics_213rr():
    fields = [
        {"pdf_field": "IncidentName",         "source": "incident.name"},
        {"pdf_field": "DateTimeOrdered",      "source": dt("prepared_by.date_time")},
        {"pdf_field": "DateTimeNeeded",       "source": s("tasks.0.due_time")},
        {"pdf_field": "RequestedByName",      "source": "prepared_by.name"},
        {"pdf_field": "RequestedByPosition",  "source": "prepared_by.position"},
        # Requested resources — user fills most of these
        *[{"pdf_field": f"ResourceType{i+1}",     "source": s(f"resource_types.{i}.name")}                  for i in range(6)],
        *[{"pdf_field": f"ResourceKind{i+1}",     "source": s(f"resource_types.{i}.category")}              for i in range(6)],
        *[{"pdf_field": f"ResourceDescription{i+1}", "source": s(f"resource_types.{i}.planning_display_name")} for i in range(6)],
        {"pdf_field": "DeliveryLocation",     "source": s("incident.icp_location")},
        {"pdf_field": "LogisticsChief",       "source": s("organization.logistics_section_chief.name")},
        {"pdf_field": "FinanceChief",         "source": s("organization.finance_admin_section_chief.name")},
        {"pdf_field": "OperationsChief",      "source": s("organization.operations_section_chief.name")},
        {"pdf_field": "PreparedBy",           "source": "prepared_by.name"},
        {"pdf_field": "PreparedDateTime",     "source": dt("prepared_by.date_time")},
    ]
    write("ics_213rr", "ICS 213RR Resource Request Message — FEMA", fields)


# ---------------------------------------------------------------------------
# ICS 214 — Activity Log  (already correct, skip)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ICS 215 — Operational Planning Worksheet
# ---------------------------------------------------------------------------
def gen_ics_215():
    rows = []
    for i in range(8):
        rows += [
            {"pdf_field": f"BranchDivGroup{i+1}",     "source": s(f"tasks.{i}.assignment")},
            {"pdf_field": f"WorkAssignment{i+1}",     "source": s(f"tasks.{i}.title")},
            {"pdf_field": f"ResourceType{i+1}",       "source": s(f"tasks.{i}.category")},
            {"pdf_field": f"ReportingLocation{i+1}",  "source": s(f"tasks.{i}.location")},
            {"pdf_field": f"OverheadPosition{i+1}",   "source": s(f"tasks.{i}.team_leader")},
        ]
    fields = [
        {"pdf_field": "IncidentName",       "source": "incident.name"},
        {"pdf_field": "IncidentNumber",     "source": s("incident.number")},
        *op_period_block(),
        {"pdf_field": "OperationsChief",    "source": s("organization.operations_section_chief.name")},
        {"pdf_field": "PlanningChief",      "source": s("organization.planning_section_chief.name")},
        *rows,
        {"pdf_field": "PreparedBy",         "source": "prepared_by.name"},
        {"pdf_field": "PreparedDateTime",   "source": dt("prepared_by.date_time")},
    ]
    write("ics_215", "ICS 215 Operational Planning Worksheet — FEMA", fields)


# ---------------------------------------------------------------------------
# ICS 215A — IAP Safety Analysis
# ---------------------------------------------------------------------------
def gen_ics_215a():
    rows = []
    for i in range(8):
        rows += [
            {"pdf_field": f"BranchDivGroup{i+1}",  "source": s(f"tasks.{i}.assignment")},
            {"pdf_field": f"WorkAssignment{i+1}",  "source": s(f"tasks.{i}.title")},
            {"pdf_field": f"Hazard{i+1}",          "source": s(f"objectives.{i}.text")},
        ]
    fields = [
        {"pdf_field": "IncidentName",       "source": "incident.name"},
        {"pdf_field": "IncidentNumber",     "source": s("incident.number")},
        *op_period_block(),
        *rows,
        {"pdf_field": "SafetyOfficer",      "source": s("organization.safety_officer.name")},
        {"pdf_field": "PreparedBy",         "source": "prepared_by.name"},
        {"pdf_field": "PreparedDateTime",   "source": dt("prepared_by.date_time")},
    ]
    write("ics_215a", "ICS 215A IAP Safety Analysis — FEMA", fields)


# ---------------------------------------------------------------------------
# ICS 218 — Support Vehicle / Equipment Inventory
# ---------------------------------------------------------------------------
def gen_ics_218():
    rows = []
    for i in range(12):
        rows += [
            {"pdf_field": f"VehicleType{i+1}",      "source": s(f"master_vehicles.{i}.make")},
            {"pdf_field": f"VehicleModel{i+1}",     "source": s(f"master_vehicles.{i}.model")},
            {"pdf_field": f"LicensePlate{i+1}",     "source": s(f"master_vehicles.{i}.license_plate")},
            {"pdf_field": f"Organization{i+1}",     "source": s(f"master_vehicles.{i}.organization")},
        ]
    fields = [
        {"pdf_field": "IncidentName",    "source": "incident.name"},
        {"pdf_field": "IncidentNumber",  "source": s("incident.number")},
        *op_period_block(),
        *rows,
        {"pdf_field": "PreparedBy",      "source": "prepared_by.name"},
        {"pdf_field": "PreparedDateTime","source": dt("prepared_by.date_time")},
    ]
    write("ics_218", "ICS 218 Support Vehicle / Equipment Inventory — FEMA", fields)


# ---------------------------------------------------------------------------
# ICS 220 — Air Operations Summary
# ---------------------------------------------------------------------------
def gen_ics_220():
    rows = []
    for i in range(5):
        rows += [
            {"pdf_field": f"TailNumber{i+1}",       "source": s(f"aircraft.{i}.tail_number")},
            {"pdf_field": f"Callsign{i+1}",         "source": s(f"aircraft.{i}.callsign")},
            {"pdf_field": f"AircraftType{i+1}",     "source": s(f"aircraft.{i}.type")},
            {"pdf_field": f"Organization{i+1}",     "source": s(f"aircraft.{i}.organization")},
            {"pdf_field": f"AssignedBase{i+1}",     "source": s(f"aircraft.{i}.base")},
            {"pdf_field": f"AssignedMission{i+1}",  "source": s(f"aircraft.{i}.assigned_team_name")},
            {"pdf_field": f"FuelType{i+1}",         "source": s(f"aircraft.{i}.fuel_type")},
        ]
    fields = [
        {"pdf_field": "IncidentName",           "source": "incident.name"},
        {"pdf_field": "IncidentNumber",         "source": s("incident.number")},
        *op_period_block(),
        {"pdf_field": "AirOpsBranchDirector",   "source": s("organization.air_operations_branch_director.name")},
        {"pdf_field": "AirTacticalSupervisor",  "source": s("organization.air_operations_branch_director.name")},
        *rows,
        {"pdf_field": "PreparedBy",             "source": "prepared_by.name"},
        {"pdf_field": "PreparedDateTime",       "source": dt("prepared_by.date_time")},
    ]
    write("ics_220", "ICS 220 Air Operations Summary — FEMA", fields)


# ---------------------------------------------------------------------------
# ICS 221 — Demobilization Check-Out
# ---------------------------------------------------------------------------
def gen_ics_221():
    fields = [
        {"pdf_field": "IncidentName",         "source": "incident.name"},
        {"pdf_field": "IncidentNumber",       "source": s("incident.number")},
        {"pdf_field": "DemobGroupName",       "source": s("teams.0.name")},
        {"pdf_field": "ResourceName",         "source": s("teams.0.name")},
        {"pdf_field": "ResourceLeader",       "source": s("teams.0.leader_name")},
        {"pdf_field": "DemobUnitLeader",      "source": s("organization.demobilization_unit_leader.name")},
        {"pdf_field": "LogisticsChief",       "source": s("organization.logistics_section_chief.name")},
        {"pdf_field": "FinanceChief",         "source": s("organization.finance_admin_section_chief.name")},
        {"pdf_field": "PreparedBy",           "source": "prepared_by.name"},
        {"pdf_field": "PreparedDateTime",     "source": dt("prepared_by.date_time")},
    ]
    write("ics_221", "ICS 221 Demobilization Check-Out — FEMA", fields)


# ---------------------------------------------------------------------------
# CAPF 104 — Mission Flight Plan
# ---------------------------------------------------------------------------
def gen_capf_104():
    fields = [
        {"pdf_field": "IncidentName",       "source": "incident.name"},
        {"pdf_field": "MissionNumber",      "source": s("incident.number")},
        {"pdf_field": "MissionDate",        "source": date("op_period.start")},
        {"pdf_field": "TailNumber",         "source": s("aircraft.0.tail_number")},
        {"pdf_field": "Callsign",           "source": s("aircraft.0.callsign")},
        {"pdf_field": "AircraftType",       "source": s("aircraft.0.type")},
        {"pdf_field": "AircraftMakeModel",  "source": {"join": [s("aircraft.0.make"), s("aircraft.0.model")], "separator": " "}},
        {"pdf_field": "Base",               "source": s("aircraft.0.base")},
        {"pdf_field": "FuelType",           "source": s("aircraft.0.fuel_type")},
        {"pdf_field": "SearchAssignment",   "source": s("tasks.0.assignment")},
        {"pdf_field": "SearchArea",         "source": s("tasks.0.location")},
        {"pdf_field": "PIC",                "source": s("personnel.0.name")},
        {"pdf_field": "MissionCoordinator", "source": s("organization.air_operations_branch_director.name")},
        {"pdf_field": "ICName",             "source": s("organization.incident_commander.name")},
        {"pdf_field": "PreparedBy",         "source": "prepared_by.name"},
        {"pdf_field": "PreparedDateTime",   "source": dt("prepared_by.date_time")},
    ]
    write("capf_104", "CAPF 104 Mission Flight Plan — FEMA", fields)


# ---------------------------------------------------------------------------
# CAPF 109 — Operational Sortie Report
# ---------------------------------------------------------------------------
def gen_capf_109():
    fields = [
        {"pdf_field": "IncidentName",         "source": "incident.name"},
        {"pdf_field": "MissionNumber",        "source": s("incident.number")},
        {"pdf_field": "SortieDate",           "source": date("op_period.start")},
        {"pdf_field": "TailNumber",           "source": s("aircraft.0.tail_number")},
        {"pdf_field": "Callsign",             "source": s("aircraft.0.callsign")},
        {"pdf_field": "AircraftType",         "source": s("aircraft.0.type")},
        {"pdf_field": "TaskID",               "source": s("tasks.0.task_id")},
        {"pdf_field": "SearchArea",           "source": s("tasks.0.location")},
        {"pdf_field": "TeamLeader",           "source": s("tasks.0.team_leader")},
        {"pdf_field": "RadioPrimary",         "source": s("tasks.0.radio_primary")},
        {"pdf_field": "PreparedBy",           "source": "prepared_by.name"},
        {"pdf_field": "PreparedDateTime",     "source": dt("prepared_by.date_time")},
    ]
    write("capf_109", "CAPF 109 Operational Sortie Report — FEMA", fields)


# ---------------------------------------------------------------------------
# SAR 104 — Search Assignment
# ---------------------------------------------------------------------------
def gen_sar_104():
    fields = [
        {"pdf_field": "IncidentName",     "source": "incident.name"},
        {"pdf_field": "IncidentNumber",   "source": s("incident.number")},
        *op_period_block(),
        {"pdf_field": "TaskID",           "source": s("tasks.0.task_id")},
        {"pdf_field": "AssignmentArea",   "source": s("tasks.0.location")},
        {"pdf_field": "Assignment",       "source": s("tasks.0.assignment")},
        {"pdf_field": "TeamName",         "source": s("teams.0.name")},
        {"pdf_field": "TeamLeader",       "source": s("tasks.0.team_leader")},
        {"pdf_field": "TeamPhone",        "source": s("tasks.0.team_phone")},
        {"pdf_field": "RadioPrimary",     "source": s("tasks.0.radio_primary")},
        {"pdf_field": "RadioAlternate",   "source": s("tasks.0.radio_alternate")},
        {"pdf_field": "RadioEmergency",   "source": s("tasks.0.radio_emergency")},
        {"pdf_field": "DueTime",          "source": s("tasks.0.due_time")},
        # Subject info
        {"pdf_field": "SubjectName",      "source": s("subject.name")},
        {"pdf_field": "SubjectSex",       "source": s("subject.sex")},
        {"pdf_field": "SubjectDOB",       "source": s("subject.dob")},
        {"pdf_field": "SubjectLKPPlace",  "source": s("subject.lkp_place")},
        {"pdf_field": "SubjectLKPTime",   "source": s("subject.lkp_time")},
        # Operations chief
        {"pdf_field": "OperationsChief",  "source": s("organization.operations_section_chief.name")},
        {"pdf_field": "PreparedBy",       "source": "prepared_by.name"},
        {"pdf_field": "PreparedDateTime", "source": dt("prepared_by.date_time")},
    ]
    write("sar_104", "SAR 104 Search Assignment — FEMA", fields)


# ---------------------------------------------------------------------------
# Run everything
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Generating / updating FEMA mapping files...\n")

    # Skip: ics_205, ics_213, ics_214 — already correct and tested
    gen_ics_201()
    gen_ics_202()
    gen_ics_203()
    gen_ics_204()
    gen_ics_205a()
    gen_ics_206()
    gen_ics_207()
    gen_ics_208()
    gen_ics_209()
    gen_ics_210()
    gen_ics_211()
    gen_ics_213rr()
    gen_ics_215()
    gen_ics_215a()
    gen_ics_218()
    gen_ics_220()
    gen_ics_221()
    gen_capf_104()
    gen_capf_109()
    gen_sar_104()

    print("\nDone.")
