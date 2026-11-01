"""Exact mappings for the bundled templates; no guessed form fields or signatures."""
from __future__ import annotations
from typing import Any
from .context import human_time
from .models import ExportSnapshot


def build_sheets(snapshot: ExportSnapshot) -> list[dict[str, Any]]:
    form = snapshot.form_id
    incident, period = snapshot.incident, snapshot.period
    start, end = period.get("start_time"), period.get("end_time")
    op = {"Date From": human_time(start, "date"), "Date To": human_time(end, "date"), "Time From": human_time(start, "time"), "Time To": human_time(end, "time")}
    def chunks(rows: list, size: int) -> list[list]:
        return [rows[i:i + size] for i in range(0, len(rows), size)] or [[]]
    if form == "ics_202":
        return [{"1 Incident Name_5": incident.get("name", ""), **op,
                 "3 Objectives": "\n".join(f"{r.get('code', '')} {r.get('text', '')}".strip() for r in snapshot.records),
                 "4 Operational Period Command Emphasis": period.get("objectives", ""),
                 "General Situational Awareness": "\n".join(str(period.get(k) or "") for k in ["weather_summary", "safety_message"]).strip(),
                 "7 Prepared by Name": snapshot.prepared_by}]
    if form == "ics_213rr":
        request = snapshot.records[0]
        sheets = []
        # A header-only request still exports its actual title as the requested need.
        items = list(request.get("items") or [])
        if not items:
            items = [{"description": request.get("title", "")}]
        for rows in chunks(items, 9):
            fields: dict[str, Any] = {
                "1. Incident Name": incident.get("name", ""), "2 DateTime": human_time(request.get("created_utc")),
                "3 Resource Request Number": str(request.get("id", "")).upper(),
                "5 Requested DeliveryReporting Location": request.get("delivery_location", ""),
                "7 Requested by NamePosition": request.get("created_by_id", ""),
                "13 Notes": "\n".join(str(request.get(k) or "") for k in ["title", "justification", "comms_requirements"]).strip(),
                "8. Priority: Urgent": request.get("priority") == "IMMEDIATE",
                "8. Priority: Routine": request.get("priority") == "ROUTINE",
            }
            for n, row in enumerate(rows, 1):
                fields.update({f"QtyRow{n}": row.get("quantity", ""), f"KindRow{n}": row.get("kind", ""),
                               f"Detailed Item Description Vital characteristics brand specs experience size etcRow{n}": " ".join(str(row.get(k) or "") for k in ["description", "unit", "special_instructions"]).strip(),
                               f"Arrival Date/Time: RequestedRow{n}": human_time(request.get("needed_by_utc"))})
            sheets.append(fields)
        return sheets
    if form == "ics_213rr_wa":
        assignment = snapshot.records[0]
        gapped = [r for r in assignment.get("resources", []) if int(r.get("quantity_gap") or 0) > 0]
        items = gapped or [{"description": "No outstanding resource gaps."}]
        sheets = []
        for rows in chunks(items, 9):
            fields: dict[str, Any] = {
                "1. Incident Name": incident.get("name", ""),
                "2 DateTime": human_time(assignment.get("updated_at") or assignment.get("created_at")),
                "3 Resource Request Number": str(assignment.get("assignment_number", "")).upper(),
                "5 Requested DeliveryReporting Location": assignment.get("location", ""),
                "7 Requested by NamePosition": assignment.get("prepared_by") or snapshot.prepared_by,
                "13 Notes": "\n".join(str(assignment.get(k) or "") for k in
                                       ["assignment_name", "tactics_summary", "special_instructions"]).strip(),
                "8. Priority: Urgent": assignment.get("priority") in ("High", "Urgent"),
                "8. Priority: Routine": assignment.get("priority") in ("Low", "Normal"),
            }
            for n, row in enumerate(rows, 1):
                # KindRow is a narrow field meant for a short ICS resource
                # category (PERSONNEL/EQUIPMENT/SUPPLY/...); a work
                # assignment's resource requirement doesn't carry one, so
                # the full resource type goes in the (overflow-capable)
                # description field instead of truncating to "...".
                fields.update({
                    f"QtyRow{n}": row.get("quantity_gap", ""),
                    f"KindRow{n}": "",
                    f"Detailed Item Description Vital characteristics brand specs experience size etcRow{n}":
                        " ".join(str(row.get(k) or "") for k in
                                 ["resource_type_text", "capability_text", "unit", "source_note", "notes", "description"]).strip(),
                    f"Arrival Date/Time: RequestedRow{n}": "",
                })
            sheets.append(fields)
        return sheets
    if form == "ics_204":
        assignment = snapshot.records[0]
        assigned = [r for requirement in assignment.get("resources", []) for r in requirement.get("assignments", [])]
        sheets = []
        for rows in chunks(assigned, 10):
            fields = {"1 Incident Name_7": incident.get("name", ""), **op, "3 Branch": assignment.get("branch", ""),
                      "3 Division": assignment.get("division_group", ""), "3 Staging Area": assignment.get("location", ""),
                      "6 Work Assignments": "\n".join(str(assignment.get(k) or "") for k in ["assignment_number", "assignment_name", "description", "tactics_summary"]).strip(),
                      "7 Special Instructions": assignment.get("special_instructions", ""), "9 Prepared by Name_2": assignment.get("prepared_by") or snapshot.prepared_by}
            for n, row in enumerate(rows, 1):
                fields[f"Resource IdentifierRow{n}_2"] = row.get("display_name", "")
            for n, comms in enumerate(assignment.get("comms", [])[:4], 1):
                fields[f"Name/Function{n}"] = comms.get("function", "")
                fields[f"Primary Contact  indicate cell pager or radio frequencysystemchannel {n}"] = " / ".join(str(comms.get(k) or "") for k in ["channel_name", "rx_freq", "tx_freq"]).strip(" / ")
            sheets.append(fields)
        return sheets
    if form == "ics_215a":
        assignment = snapshot.records[0]
        sheets = []
        for rows in chunks(assignment.get("hazards", []), 14):
            fields = {"1 Incident Name_21": incident.get("name", ""), "2 Incident Number_10": incident.get("incident_number", ""), **op}
            for n, row in enumerate(rows, 1):
                fields.update({f"5 Incident AreaRow{n}": assignment.get("location", ""), f"6 HazardsRisksRow{n}": row.get("hazard_type_text", ""),
                               f"7 MitigationsRow{n}": "\n".join(str(row.get(k) or "") for k in ["control_measure", "mitigation_text", "ppe_text", "safety_message"]).strip()})
            sheets.append(fields)
        return sheets
    if form == "ics_211":
        sheets = []
        for rows in chunks(snapshot.records, 8):
            fields = {"1 Incident Name": incident.get("name", ""), "2 Incident Number": incident.get("incident_number", ""), "Start Date": human_time(start, "date"), "Start Time": human_time(start, "time"), "Name": snapshot.prepared_by}
            for n, row in enumerate(rows, 1):
                fields.update({f"R{n} Resource Name or ID {n}": row.get("resource_name", ""), f"R{n} Kind {n}": row.get("entity_type", ""), f"R{n} Date/Time Check In {n}": human_time(row.get("checked_in_time")), f"R{n} Incident Assignment {n}": row.get("assigned_to", "")})
            sheets.append(fields)
        return sheets
    if form == "ics_230":
        fixed_rows = {
            "objectives-meeting": 2,
            "command-general-staff": 4,
            "tactics": 6,
            "planning": 8,
            "operations-briefing": 10,
        }
        title_rows = {
            "objectives meeting": 2,
            "command and general staff meeting": 4,
            "command & general staff meeting": 4,
            "tactics meeting": 6,
            "planning meeting": 8,
            "operations briefing": 10,
        }
        fixed: dict[int, dict[str, Any]] = {}
        open_meetings: list[dict[str, Any]] = []
        for meeting in snapshot.records:
            slug = str(meeting.get("meeting_type") or meeting.get("meeting_type_slug") or "").strip().lower()
            title = str(meeting.get("title") or meeting.get("meeting_name") or "").strip().lower()
            row_number = fixed_rows.get(slug) or title_rows.get(title)
            if row_number and row_number not in fixed:
                fixed[row_number] = meeting
            else:
                open_meetings.append(meeting)

        sheets = []
        open_rows = [1, 3, 5, 7, 9, 11, 12]
        for rows in chunks(open_meetings, len(open_rows)):
            fields = {"1 Incident Name": incident.get("name", ""), "2 Operational Period DateTime: From": human_time(start), "2 Operational Period DateTime: To:": human_time(end), "4 Prepared by Situation Unit Leader DateTime": snapshot.prepared_by}
            meetings = {**fixed, **dict(zip(open_rows, rows))}
            for n, row in meetings.items():
                attendees = ", ".join(
                    str(a.get("display_name") or a.get("name") or a.get("role") or "")
                    for a in row.get("attendees", [])
                    if isinstance(a, dict)
                )
                fields.update({f"Meeting NameRow{n}": row.get("title") or row.get("meeting_name", ""), f"Date TimeRow{n}": f"{row.get('meeting_date', '')} {row.get('start_time', '')} - {row.get('end_time', '')}".strip(),
                               f"PurposeRow{n}": row.get("freeform_notes") or row.get("purpose", ""), f"AttendeesRow{n}": attendees, f"LocationRow{n}": row.get("virtual_link") or row.get("location", "")})
            sheets.append(fields)
        return sheets
    if form == "ics_209":
        record = snapshot.records[0]
        narrative = "\n\n".join(f"{s.get('title', '')}\n{s.get('edited_content') or s.get('auto_content') or ''}".strip() for s in record.get("sections", []))
        return [{"1 INCIDENT NAME": incident.get("name", ""), "*1. INCIDENT NAME": incident.get("name", ""), "2 INCIDENT NO": incident.get("incident_number", ""), "2. INCIDENT NO": incident.get("incident_number", ""),
                 "*3. REPORT VERSION Rpt# (if used)": record.get("sitrep_number", ""), "*11. FOR TIME PERIOD From Date/Time": human_time(start), "*11. TO TIME PERIOD To Date/Time": human_time(end),
                 "*12 PREPARED BY Print Name": record.get("prepared_by") or snapshot.prepared_by, "*12 PREPARED BY Date/Time Prepared": human_time(record.get("created_at")),
                 "*28. SIGNIFICANT EVENTS FOR THE TIME PERIOD REPORTED": record.get("summary", ""), "47. REMARKS": narrative}]
    if form == "ics_215":
        assignment = snapshot.records[0]
        fields = {"Text32": incident.get("name", ""), "Text34.0.0": human_time(start, "date"), "Text34.0.1": human_time(end, "date"), "Text34.1.0": human_time(start, "time"), "Text34.1.1": human_time(end, "time"),
                  "1 Incident NameRow2": assignment.get("branch", ""), "1 Incident NameRow2_2": assignment.get("division_group", ""),
                  "5 Work Assignment  Special InstructionsRow1": "\n".join(str(assignment.get(k) or "") for k in ["assignment_name", "description", "special_instructions"]).strip(),
                  "Text30.0.0": assignment.get("location", ""), "Text33.0": assignment.get("prepared_by") or snapshot.prepared_by}
        sheets = []
        requirements = assignment.get("resources", [])
        headers = ["Text24.0.0", "Text24.0.1"] + [f"Text24.{n}" for n in range(1, 11)]
        for rows in chunks(requirements, 12):
            sheet = dict(fields)
            for column, requirement in enumerate(rows):
                sheet[headers[column]] = requirement.get("resource_type_text", "")
                for row, key in enumerate(["quantity_required", "quantity_available", "quantity_gap"]):
                    sheet[f"Text26.{row}.{column}"] = requirement.get(key, "")
            sheets.append(sheet)
        return sheets
    raise ValueError("Unsupported form")
