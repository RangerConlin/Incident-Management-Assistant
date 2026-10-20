"""Headless ICS 203 context from canonical embedded organization assignments."""
from __future__ import annotations

import re
from typing import Any

from sarapp_db.mongo.collection_names import IncidentCollections as C, MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from .context import ExportReadRepository, human_time
from .models import ExportError, ExportSnapshot
from .bindings import lookup_path, resolve_fields, resolve_row


ROLE_KEYS = {
    "Incident Commander": "incident_commander",
    "Deputy Incident Commander": "deputy_incident_commander",
    "Safety Officer": "safety_officer",
    "Public Information Officer": "public_information_officer",
    "Liaison Officer": "liaison_officer",
    "Operations Section Chief": "operations_section_chief",
    "Deputy Operations Section Chief": "deputy_operations_section_chief",
    "Planning Section Chief": "planning_section_chief",
    "Deputy Planning Section Chief": "deputy_planning_section_chief",
    "Logistics Section Chief": "logistics_section_chief",
    "Deputy Logistics Section Chief": "deputy_logistics_section_chief",
    "Finance/Admin Section Chief": "finance_admin_section_chief",
    "Deputy Finance/Admin Section Chief": "deputy_finance_admin_section_chief",
    "Communications Unit Leader": "communications_unit_leader",
    "Medical Unit Leader": "medical_unit_leader",
    "Ground Support Unit Leader": "ground_support_unit_leader",
    "Food Unit Leader": "food_unit_leader",
    "Facilities Unit Leader": "facilities_unit_leader",
    "Supply Unit Leader": "supply_unit_leader",
    "Air Operations Branch Director": "air_operations_branch_director",
    "Air Tactical Group Supervisor": "air_tactical_group_supervisor",
    "Air Support Group Supervisor": "air_support_group_supervisor",
    "Service Branch Director": "service_branch_director",
    "Support Branch Director": "support_branch_director",
    "Staging Area Manager": "staging_area_manager",
    "Intelligence Section Chief": "intelligence_section_chief",
    "Deputy Intelligence Section Chief": "deputy_intelligence_section_chief",
    "Collection Coordinator": "collection_coordinator",
    "Intelligence Operations Coordinator": "intelligence_operations_coordinator",
    "Dissemination Manager": "dissemination_manager",
    "Situation Unit Leader": "situation_unit_leader",
    "Resources Unit Leader": "resources_unit_leader",
    "Documentation Unit Leader": "documentation_unit_leader",
    "Demobilization Unit Leader": "demobilization_unit_leader",
    "Environmental Unit Leader": "environmental_unit_leader",
    "Time Unit Leader": "time_unit_leader",
    "Procurement Unit Leader": "procurement_unit_leader",
    "Compensation/Claims Unit Leader": "compensation_claims_unit_leader",
    "Cost Unit Leader": "cost_unit_leader",
    "Air Operations Branch": "air_operations_branch_director",
    "Finance/Administration Section Chief": "finance_admin_section_chief",
    "Deputy Finance/Administration Section Chief": "deputy_finance_admin_section_chief",
}


def load_organization(
    db: Any, positions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Resolve only personnel referenced by current, unended assignments."""
    ids = {
        assignment["person_record"]
        for position in positions
        for bucket in ("primary", "deputies", "staff_assistants")
        for assignment in position.get(bucket, [])
        if assignment.get("end_time") is None
    }
    people = {}
    if ids:
        rows = ExportReadRepository(get_master_db(), MasterCollections.PERSONNEL).find_many(
            {"person_record": {"$in": list(ids)}}
        )
        people = {row["person_record"]: row for row in rows}
        if ids - people.keys():
            raise ExportError(422, "An organization assignee is missing from master personnel")

    def names(position: dict, bucket: str = "primary") -> str:
        return "; ".join(
            str(people[a["person_record"]].get("name") or "")
            + (" (Trainee)" if a.get("trainee") else "")
            for a in position.get(bucket, []) if a.get("end_time") is None
        )

    organization: dict[str, Any] = {}
    commanders = []
    specialists = []
    all_positions = []
    for position in positions:
        title = position.get("title", "")
        primary = names(position)
        deputies = names(position, "deputies")
        assistants = names(position, "staff_assistants")
        all_positions.append({"title": title, "primary": primary,
                              "deputies": deputies, "staff_assistants": assistants})
        key = ROLE_KEYS.get(title)
        if key:
            # Multiple matching positions/assignees are retained, never first-only.
            label = "; ".join(filter(None, [
                primary, f"Staff assistant: {assistants}" if assistants else "",
            ]))
            previous = organization.get(key, {}).get("name", "")
            organization[key] = {"name": "; ".join(filter(None, [previous, label]))}
            deputy_key = "deputy_" + key
            if deputies:
                previous = organization.get(deputy_key, {}).get("name", "")
                organization[deputy_key] = {"name": "; ".join(filter(None, [previous, deputies]))}
        if title == "Incident Commander":
            for a in position.get("primary", []):
                if a.get("end_time") is None:
                    person = people[a["person_record"]]
                    commanders.append({
                        "name": str(person.get("name") or "")
                        + (" (Trainee)" if a.get("trainee") else ""),
                        "agency": person.get("organization", ""),
                    })
        if "technical specialist" in title.casefold():
            specialists.append({"name": primary, "specialty": title.partition("-")[2].strip()})

    branches = []
    sorted_positions = sorted(
        positions, key=lambda p: (p.get("sort_order") or 0, p.get("title") or "")
    )
    for position in sorted_positions:
        if (position.get("classification") != "branch"
                or "air operations" in position.get("title", "").casefold()):
            continue
        divisions = [
            {"name": child.get("title", ""), "supervisor_name": names(child)}
            for child in sorted_positions
            if child.get("parent_position_id") == position["position_id"]
            and child.get("classification") in {"division", "group"}
        ]
        branches.append({
            "name": position.get("title", ""), "director_name": names(position),
            "deputy_name": names(position, "deputies"), "divisions": divisions,
        })

    agencies = ExportReadRepository(db, C.LIAISON_AGENCIES).find_many(
        {"deleted": {"$ne": True}}, sort=[("int_id", 1)]
    )
    agency_names = {row["int_id"]: row.get("name", "") for row in agencies}
    contacts = ExportReadRepository(db, C.LIAISON_CONTACTS).find_many(
        {"agency_id": {"$in": list(agency_names)}, "deleted": {"$ne": True}}, sort=[("int_id", 1)]
    )
    return {"organization": organization, "uc_commanders": commanders,
            "org_branches": branches, "planning_tech_specialists": specialists,
            "org_agency_reps": [
                {"name": c.get("name", ""), "agency": agency_names[c["agency_id"]]}
                for c in contacts
            ],
            "current_positions": all_positions}


def build_203_sheets(snapshot: ExportSnapshot, mapping: dict[str, Any]) -> list[dict[str, Any]]:
    """Resolve approved per-set form bindings and paginate repeating sections."""
    if snapshot.form_set_id not in {"fema", "ics_canada", "uscg"}:
        raise ValueError("Unsupported ICS 203 form set")
    data = snapshot.records[0] if snapshot.records else {}
    groups: dict[str, int] = {}
    for field in mapping["fields"]:
        source = field["source"]
        path = source.get("key", "") if isinstance(source, dict) else source
        match = re.match(
            r"(uc_commanders|org_agency_reps|org_branches|planning_tech_specialists)\.(\d+)\.",
            path,
        )
        if match:
            key, slot = match.groups()
            groups[key] = max(groups.get(key, 0), int(slot) + 1)
    for group in mapping.get("row_groups", []):
        key = group["data_key"]
        slots = sum(group["rows_per_page"])
        # Use the smaller specialty/name capacity so both stay on the same sheet.
        if key == "planning_tech_specialists":
            groups[key] = min(groups.get(key, slots), slots)
        else:
            groups[key] = max(groups.get(key, slots), slots)
    count = max([1] + [(len(data.get(key, [])) + size - 1) // size for key, size in groups.items()])
    branch_pages = []
    branch_slots = groups.get("org_branches", 3)
    division_slots = 6 if snapshot.form_set_id == "uscg" else 5
    branches = data.get("org_branches", [])
    for offset in range(0, len(branches), branch_slots):
        batch = branches[offset:offset + branch_slots]
        pages = max([1] + [
            (len(b.get("divisions", [])) + division_slots - 1) // division_slots
            for b in batch
        ])
        for page in range(pages):
            start = page * division_slots
            end = start + division_slots
            branch_pages.append([
                {**branch, "divisions": branch.get("divisions", [])[start:end]}
                for branch in batch
            ])
    count = max(count, len(branch_pages))

    sheets = []
    for index in range(count):
        context = {**data, "incident": snapshot.incident,
                   "op_period": {"start": snapshot.period.get("start_time"),
                                 "end": snapshot.period.get("end_time"),
                                 "start_date": human_time(snapshot.period.get("start_time"), "date_short"),
                                 "end_date": human_time(snapshot.period.get("end_time"), "date_short"),
                                 "start_time": human_time(snapshot.period.get("start_time"), "time_short"),
                                 "end_time": human_time(snapshot.period.get("end_time"), "time_short")},
                   "prepared_by": {"name": snapshot.prepared_by,
                                   "position": snapshot.prepared_by_position,
                                   "date_time": snapshot.generated_at}}
        for key, size in groups.items():
            context[key] = data.get(key, [])[index * size:(index + 1) * size]
        context["org_branches"] = branch_pages[index] if index < len(branch_pages) else []
        # The first commander occupies the dedicated IC slot on each sheet.
        organization = dict(data.get("organization", {}))
        organization["incident_commander"] = {"name": lookup_path(context, "uc_commanders.0.name") or ""}
        context["organization"] = organization
        fields = resolve_fields(mapping, context)
        # A plain prepared-by timestamp path has historically been human readable.
        for field in mapping["fields"]:
            if field["source"] == "prepared_by.date_time":
                fields[field["pdf_field"]] = human_time(snapshot.generated_at, "datetime_human")
        for group in mapping.get("row_groups", []):
            rows = context.get(group["data_key"], [])[:sum(group["rows_per_page"])]
            for row_index, row in enumerate(rows, 1):
                fields.update(resolve_row(group, row, row_index))
        sheets.append(fields)
    return sheets
