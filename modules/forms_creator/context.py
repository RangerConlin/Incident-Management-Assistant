"""Build a nested data dict for PDF form filling from the SARApp API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from utils import incident_context
from utils.api_client import api_client


def _fmt_date(dt_str: str | None) -> str:
    if not dt_str:
        return ""
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(dt_str[:19], fmt[:len(dt_str[:19])]).strftime("%m/%d/%Y")
        except ValueError:
            continue
    return ""


def _fmt_time(dt_str: str | None) -> str:
    if not dt_str:
        return ""
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(dt_str[:19], fmt[:len(dt_str[:19])]).strftime("%H%M")
        except ValueError:
            continue
    return ""


def _get(path: str, **params) -> Any:
    try:
        return api_client.get(path, params=params or None)
    except Exception:
        return None


class FormDataContext:
    """Assemble a nested dict from the active incident and master API."""

    _ORG_POSITIONS: dict[str, str] = {
        # Command
        "Incident Commander":                    "incident_commander",
        "Deputy Incident Commander":             "deputy_incident_commander",
        # Command Staff
        "Safety Officer":                        "safety_officer",
        "Public Information Officer":            "public_information_officer",
        "Liaison Officer":                       "liaison_officer",
        # Section Chiefs + Deputies
        "Operations Section Chief":              "operations_section_chief",
        "Deputy Operations Section Chief":       "deputy_operations_section_chief",
        "Planning Section Chief":                "planning_section_chief",
        "Deputy Planning Section Chief":         "deputy_planning_section_chief",
        "Logistics Section Chief":               "logistics_section_chief",
        "Deputy Logistics Section Chief":        "deputy_logistics_section_chief",
        "Finance/Admin Section Chief":           "finance_admin_section_chief",
        "Deputy Finance/Admin Section Chief":    "deputy_finance_admin_section_chief",
        # Logistics Section units
        "Communications Unit Leader":            "communications_unit_leader",
        "Medical Unit Leader":                   "medical_unit_leader",
        "Ground Support Unit Leader":            "ground_support_unit_leader",
        "Food Unit Leader":                      "food_unit_leader",
        "Facilities Unit Leader":                "facilities_unit_leader",
        "Supply Unit Leader":                    "supply_unit_leader",
        # Operations Section
        "Air Operations Branch Director":        "air_operations_branch_director",
        "Air Tactical Group Supervisor":         "air_tactical_group_supervisor",
        "Air Support Group Supervisor":          "air_support_group_supervisor",
        "Service Branch Director":               "service_branch_director",
        "Support Branch Director":               "support_branch_director",
        "Staging Area Manager":                  "staging_area_manager",
        # Intelligence / Investigations Section (CG/DHS extended ICS)
        "Intelligence Section Chief":            "intelligence_section_chief",
        "Deputy Intelligence Section Chief":     "deputy_intelligence_section_chief",
        "Collection Coordinator":                "collection_coordinator",
        "Intelligence Operations Coordinator":   "intelligence_operations_coordinator",
        "Dissemination Manager":                 "dissemination_manager",
        # Planning Section units
        "Situation Unit Leader":                 "situation_unit_leader",
        "Resources Unit Leader":                 "resources_unit_leader",
        "Documentation Unit Leader":             "documentation_unit_leader",
        "Demobilization Unit Leader":            "demobilization_unit_leader",
        # Finance/Admin Section units
        "Time Unit Leader":                      "time_unit_leader",
        "Procurement Unit Leader":               "procurement_unit_leader",
        "Compensation/Claims Unit Leader":       "compensation_claims_unit_leader",
        "Cost Unit Leader":                      "cost_unit_leader",
    }

    def build(self, incident_id: str | None = None) -> dict[str, Any]:
        """Return the full data context dict for the given incident."""
        inc_id = incident_id or incident_context.get_active_incident_id()

        data: dict[str, Any] = {}

        data["incident"]        = self._build_incident(inc_id)
        data["op_period"]       = self._build_op_period(inc_id)
        data["organization"]    = self._build_organization(inc_id)
        air_ops = self._build_air_ops_branch(inc_id)
        if air_ops["director_name"]:
            # A branch explicitly flagged is_air_ops takes priority over the
            # legacy single-named-position lookup ("Air Operations Branch
            # Director" title) above, so either path populates the same
            # organization.air_operations_branch_director.name binding.
            data["organization"]["air_operations_branch_director"] = {
                "name": air_ops["director_name"], "personnel_id": "", "title": "Air Operations Branch Director",
            }
        data["prepared_by"]     = self._build_prepared_by()

        data["channels"]        = self._build_channels(inc_id)
        data["channels_notes"]  = ""
        data["teams"]           = self._build_teams(inc_id)
        data["tasks"]           = self._build_tasks(inc_id)
        data["objectives"]      = self._build_objectives(inc_id)
        data["vehicles"]        = self._build_incident_vehicles(inc_id)
        liaison_data            = self._build_liaison_data(inc_id)
        data["liaison_agencies"] = liaison_data["liaison_agencies"]
        data["liaison_contacts"] = liaison_data["liaison_contacts"]
        data["agency_contacts"] = liaison_data["agency_contacts"]
        data["liaison_interactions"] = liaison_data["liaison_interactions"]
        data["liaison_feedback"] = liaison_data["liaison_feedback"]
        data["liaison_agency_requests"] = liaison_data["liaison_agency_requests"]
        data["liaison_resource_offers"] = liaison_data["liaison_resource_offers"]
        data["liaison_followup_actions"] = liaison_data["liaison_followup_actions"]
        data["liaison_restrictions"] = liaison_data["liaison_restrictions"]
        data["liaison_agreements"] = liaison_data["liaison_agreements"]
        data["narrative"]       = []
        data["meetings"]        = self._build_meetings(inc_id)
        data["subject"]         = {"name": "", "sex": "", "dob": "", "race": "", "lkp_place": "", "lkp_time": ""}
        data["debrief"]         = self._empty_debrief_shape()

        data["aircraft"]        = self._build_aircraft()
        data["personnel"]       = self._build_personnel()
        data["master_vehicles"] = self._build_master_vehicles()
        data["equipment"]       = self._build_equipment()
        data["hospitals"]       = []
        data["ems_agencies"]    = []
        data["comms_resources"] = self._build_comms_resources()
        data["resource_types"]  = self._build_resource_types()

        data["message"]         = {}

        data["comm_log"]        = self._build_comm_log(inc_id)

        data["uc_commanders"]              = self._build_uc_commanders(inc_id)
        data["org_branches"]               = self._build_org_branches(inc_id)   # each entry carries branch director + div slots
        data["org_agency_reps"]            = liaison_data["agency_contacts"]
        data["team_members"]               = []
        data["planning_tech_specialists"]  = self._build_planning_tech_specialists(inc_id)

        return data

    # ------------------------------------------------------------------
    # Incident
    # ------------------------------------------------------------------

    def _build_incident(self, inc_id: str | None) -> dict[str, Any]:
        empty = {"name": "", "number": "", "type": "", "description": "", "icp_location": "", "start_time": ""}
        if not inc_id:
            return empty
        try:
            doc = _get(f"/api/incidents/{inc_id}")
            if doc:
                return {
                    "id": doc.get("id", ""),
                    "name": doc.get("name", ""),
                    "number": doc.get("number", "") or doc.get("incident_number", ""),
                    "type": doc.get("type", "") or doc.get("incident_type", ""),
                    "description": doc.get("description", ""),
                    "icp_location": doc.get("icp_location", "") or doc.get("location", ""),
                    "start_time": doc.get("start_time", "") or doc.get("start_date", ""),
                }
        except Exception:
            pass
        return empty

    # ------------------------------------------------------------------
    # Operational period
    # ------------------------------------------------------------------

    def _build_op_period(self, inc_id: str | None) -> dict[str, Any]:
        empty = {
            "number": "", "start": "", "end": "",
            "start_date": "", "start_time": "", "end_date": "", "end_time": "",
        }
        if not inc_id:
            return empty
        try:
            periods = _get(f"/api/incidents/{inc_id}/operational-periods") or []
            if periods:
                row = periods[-1]
                start = row.get("start_time") or row.get("op_start") or ""
                end = row.get("end_time") or row.get("op_end") or ""
                return {
                    "number":     row.get("op_number") or row.get("number") or "",
                    "start":      start,
                    "end":        end,
                    "start_date": _fmt_date(start),
                    "start_time": _fmt_time(start),
                    "end_date":   _fmt_date(end),
                    "end_time":   _fmt_time(end),
                }
        except Exception:
            pass
        return empty

    # ------------------------------------------------------------------
    # Organization
    # ------------------------------------------------------------------

    def _build_organization(self, inc_id: str | None) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if inc_id:
            try:
                # /org/assignments only carries position_id, not the position's
                # title - join against /org/positions to resolve it. (Previously
                # this read row.get("position_title")/row.get("title"), which
                # never exists on an assignment record, so this never matched
                # anything - every organization.<role>.name path always
                # resolved empty regardless of real data.)
                positions = _get(f"/api/incidents/{inc_id}/org/positions") or []
                title_by_position_id = {
                    p.get("position_id"): p.get("title") or "" for p in positions
                }
                assignments = _get(f"/api/incidents/{inc_id}/org/assignments") or []
                seen: set[str] = set()
                for row in assignments:
                    title = title_by_position_id.get(row.get("position_id"), "")
                    key = self._ORG_POSITIONS.get(title)
                    if key and key not in seen:
                        result[key] = {
                            "name": row.get("display_name") or "",
                            "personnel_id": row.get("personnel_id") or "",
                            "title": title,
                        }
                        seen.add(key)
            except Exception:
                pass
        for key in self._ORG_POSITIONS.values():
            if key not in result:
                result[key] = {"name": "", "personnel_id": "", "title": ""}
        return result

    # ------------------------------------------------------------------
    # Unified Command members (multiple ICs sharing the "Incident
    # Commander" position - distinct from the single organization.
    # incident_commander.name slot above, which only ever holds one)
    # ------------------------------------------------------------------

    def _build_uc_commanders(self, inc_id: str | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            positions = _get(f"/api/incidents/{inc_id}/org/positions") or []
            ic_position_ids = {
                p.get("position_id")
                for p in positions
                if (p.get("title") or "").strip().lower() == "incident commander"
            }
            if not ic_position_ids:
                return []
            assignments = _get(f"/api/incidents/{inc_id}/org/assignments") or []
            personnel_by_id = self._personnel_by_id()
            result: list[dict[str, Any]] = []
            for row in assignments:
                if row.get("position_id") not in ic_position_ids:
                    continue
                personnel_id = row.get("personnel_id")
                agency = ""
                if personnel_id and personnel_id in personnel_by_id:
                    agency = personnel_by_id[personnel_id].get("home_unit") or ""
                result.append({"agency": agency, "name": row.get("display_name") or ""})
            return result
        except Exception:
            return []

    def _personnel_by_id(self) -> dict[str, dict[str, Any]]:
        try:
            rows = _get("/api/master/personnel") or []
            return {str(r.get("id")): r for r in rows if r.get("id")}
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Operations Section branches + divisions/groups (ICS 203/207)
    # ------------------------------------------------------------------

    def _build_org_branches(self, inc_id: str | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            units = _get(
                f"/api/incidents/{inc_id}/org/units",
                classifications="branch,division,group",
            ) or []
            assignments = _get(f"/api/incidents/{inc_id}/org/assignments") or []
            assign_by_position: dict[int, list[dict[str, Any]]] = {}
            for row in assignments:
                assign_by_position.setdefault(row.get("position_id"), []).append(row)

            # Air Operations Branch is excluded here even if classified as a
            # plain "branch" - it's flagged via is_air_ops (set from the
            # incident organization panel's "Air Operations Branch"
            # checkbox) and handled separately by _build_air_ops_branch, so
            # it populates the form's dedicated Air Ops field instead of
            # taking up one of the numbered Branch 1/2/3 slots.
            branches = [
                u for u in units
                if u.get("classification") == "branch" and not u.get("is_air_ops")
            ]
            branches.sort(key=lambda b: (b.get("sort_order") or 0, b.get("title") or ""))

            result: list[dict[str, Any]] = []
            for branch in branches:
                branch_pid = branch.get("position_id")
                director_name = ""
                deputy_name = ""
                for row in assign_by_position.get(branch_pid, []):
                    if row.get("assignment_type") == "deputy":
                        deputy_name = deputy_name or row.get("display_name") or ""
                    else:
                        director_name = director_name or row.get("display_name") or ""

                divisions = [
                    u for u in units
                    if u.get("classification") in ("division", "group")
                    and u.get("parent_position_id") == branch_pid
                ]
                divisions.sort(key=lambda d: (d.get("sort_order") or 0, d.get("title") or ""))

                division_list: list[dict[str, Any]] = []
                for division in divisions:
                    div_pid = division.get("position_id")
                    supervisor_name = ""
                    for row in assign_by_position.get(div_pid, []):
                        supervisor_name = row.get("display_name") or ""
                        break
                    division_list.append({
                        "name": division.get("title") or "",
                        "supervisor_name": supervisor_name,
                    })

                result.append({
                    "name": branch.get("title") or "",
                    "director_name": director_name,
                    "deputy_name": deputy_name,
                    "divisions": division_list,
                })
            return result
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Air Operations Branch (flagged via is_air_ops, not title-matched -
    # see _build_org_branches above for why it's excluded from the
    # numbered branch list)
    # ------------------------------------------------------------------

    def _build_air_ops_branch(self, inc_id: str | None) -> dict[str, str]:
        empty = {"director_name": "", "deputy_name": ""}
        if not inc_id:
            return empty
        try:
            units = _get(f"/api/incidents/{inc_id}/org/units", classifications="branch") or []
            air_ops_units = [u for u in units if u.get("is_air_ops")]
            if not air_ops_units:
                return empty
            branch_pid = air_ops_units[0].get("position_id")

            assignments = _get(f"/api/incidents/{inc_id}/org/assignments") or []
            director_name = deputy_name = ""
            for row in assignments:
                if row.get("position_id") != branch_pid:
                    continue
                if row.get("assignment_type") == "deputy":
                    deputy_name = deputy_name or row.get("display_name") or ""
                else:
                    director_name = director_name or row.get("display_name") or ""
            return {"director_name": director_name, "deputy_name": deputy_name}
        except Exception:
            return empty

    # ------------------------------------------------------------------
    # Planning Section technical specialists (ICS 203)
    # ------------------------------------------------------------------

    def _build_planning_tech_specialists(self, inc_id: str | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            positions = _get(f"/api/incidents/{inc_id}/org/positions") or []
            specialists = [
                p for p in positions
                if "technical specialist" in (p.get("title") or "").lower()
            ]
            specialists.sort(key=lambda p: (p.get("sort_order") or 0, p.get("position_id") or 0))

            assignments = _get(f"/api/incidents/{inc_id}/org/assignments") or []
            assign_by_position: dict[int, list[dict[str, Any]]] = {}
            for row in assignments:
                assign_by_position.setdefault(row.get("position_id"), []).append(row)

            result: list[dict[str, Any]] = []
            for pos in specialists:
                title = pos.get("title") or ""
                # Convention: "Technical Specialist - GIS" -> specialty "GIS".
                # A bare "Technical Specialist" position has no specialty.
                specialty = title.split("-", 1)[1].strip() if "-" in title else ""
                name = ""
                for row in assign_by_position.get(pos.get("position_id"), []):
                    name = row.get("display_name") or ""
                    break
                result.append({"name": name, "specialty": specialty})
            return result
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Channels
    # ------------------------------------------------------------------

    def _build_channels(self, inc_id: str | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            rows = _get(f"/api/incidents/{inc_id}/comms/channels") or []
            return [
                {
                    "name": r.get("channel") or r.get("name") or "",
                    "function": r.get("function") or "",
                    "rx_freq": r.get("rx_freq") or r.get("freq_rx") or "",
                    "tx_freq": r.get("tx_freq") or r.get("freq_tx") or "",
                    "rx_tone": r.get("rx_tone") or "",
                    "tx_tone": r.get("tx_tone") or "",
                    "mode": r.get("mode") or "",
                    "assignment": r.get("assignment_team") or r.get("assignment") or "",
                    "remarks": r.get("remarks") or r.get("notes") or "",
                }
                for r in rows
            ]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Teams
    # ------------------------------------------------------------------

    def _build_teams(self, inc_id: str | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            return _get(f"/api/incidents/{inc_id}/teams") or []
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def _build_tasks(self, inc_id: str | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            rows = _get(f"/api/incidents/{inc_id}/tasks") or []
            for r in rows:
                created = r.get("created_at") or ""
                r.setdefault("task_date", _fmt_date(created))
                r.setdefault("task_time", _fmt_time(created))
            return rows
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Objectives
    # ------------------------------------------------------------------

    def _build_objectives(self, inc_id: str | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            rows = _get("/api/objectives", incident_id=inc_id) or []
            return [
                {
                    "id": r.get("_id") or r.get("id") or "",
                    "description": r.get("description") or r.get("text") or "",
                    "text": r.get("text") or r.get("description") or "",
                    "status": r.get("status") or "",
                    "priority": r.get("priority") or "",
                    "assigned_section": r.get("assigned_section") or r.get("owner_section") or "",
                    "owner_section": r.get("owner_section") or "",
                    "due_time": r.get("due_time") or "",
                    "code": r.get("code") or "",
                    "display_order": r.get("display_order") or 0,
                }
                for r in rows
            ]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Vehicles (incident)
    # ------------------------------------------------------------------

    def _build_incident_vehicles(self, inc_id: str | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            return _get(f"/api/incidents/{inc_id}/resources") or []
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Liaison
    # ------------------------------------------------------------------

    def _build_liaison_data(self, inc_id: str | None) -> dict[str, list[dict[str, Any]]]:
        empty = {
            "liaison_agencies": [],
            "liaison_contacts": [],
            "agency_contacts": [],
            "liaison_interactions": [],
            "liaison_feedback": [],
            "liaison_agency_requests": [],
            "liaison_resource_offers": [],
            "liaison_followup_actions": [],
            "liaison_restrictions": [],
            "liaison_agreements": [],
        }
        if not inc_id:
            return empty
        try:
            agencies = _get(f"/api/incidents/{inc_id}/liaison/agencies") or []
            agency_names = {
                agency.get("int_id"): agency.get("name") or agency.get("agency") or ""
                for agency in agencies
                if agency.get("int_id") not in (None, "")
            }

            result = {
                **empty,
                "liaison_agencies": [self._normalize_liaison_agency(row) for row in agencies],
                "liaison_interactions": [
                    self._normalize_liaison_interaction(row, agency_names)
                    for row in (_get(f"/api/incidents/{inc_id}/liaison/interactions") or [])
                ],
                "liaison_feedback": [
                    self._normalize_liaison_feedback(row, agency_names)
                    for row in (_get(f"/api/incidents/{inc_id}/liaison/feedback") or [])
                ],
                "liaison_agency_requests": [
                    self._normalize_liaison_agency_request(row, agency_names)
                    for row in (_get(f"/api/incidents/{inc_id}/liaison/agency-requests") or [])
                ],
                "liaison_resource_offers": [
                    self._normalize_liaison_resource_offer(row, agency_names)
                    for row in (_get(f"/api/incidents/{inc_id}/liaison/resource-offers") or [])
                ],
            }

            contacts: list[dict[str, Any]] = []
            agency_contacts: list[dict[str, Any]] = []
            followups: list[dict[str, Any]] = []
            restrictions: list[dict[str, Any]] = []
            agreements: list[dict[str, Any]] = []

            for agency_id, agency_name in agency_names.items():
                detail = _get(f"/api/incidents/{inc_id}/liaison/agencies/{agency_id}/detail") or {}
                for row in detail.get("contacts") or []:
                    contact = self._normalize_liaison_contact(row, agency_name)
                    contacts.append(contact)
                    agency_contacts.append(
                        {
                            "title": contact.get("title", ""),
                            "name": contact.get("name", ""),
                            "agency": contact.get("agency", ""),
                            "phone": contact.get("phone", ""),
                            "email": contact.get("email", ""),
                            "notes": contact.get("notes", ""),
                        }
                    )
                for row in detail.get("followups") or []:
                    followups.append(self._normalize_liaison_followup_action(row, agency_names))
                for row in detail.get("restrictions") or []:
                    restrictions.append(self._normalize_liaison_restriction(row, agency_names))
                for row in detail.get("agreements") or []:
                    agreements.append(self._normalize_liaison_agreement(row, agency_names))

            result["liaison_contacts"] = contacts
            result["agency_contacts"] = agency_contacts
            result["liaison_followup_actions"] = followups
            result["liaison_restrictions"] = restrictions
            result["liaison_agreements"] = agreements
            return result
        except Exception:
            return empty

    def _normalize_liaison_agency(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "int_id": row.get("int_id") or row.get("id") or "",
            "name": row.get("name") or "",
            "agency_type": row.get("agency_type") or "",
            "jurisdiction": row.get("jurisdiction") or "",
            "current_status": row.get("current_status") or "",
            "assigned_liaison": row.get("assigned_liaison") or "",
            "last_contact": row.get("last_contact") or "",
            "next_contact_due": row.get("next_contact_due") or "",
            "priority": row.get("priority") or "",
            "notes": row.get("notes") or "",
            "created_at": row.get("created_at") or "",
            "updated_at": row.get("updated_at") or "",
        }

    def _normalize_liaison_contact(self, row: dict[str, Any], agency_name: str) -> dict[str, Any]:
        title = row.get("title") or row.get("role") or ""
        role = row.get("role") or row.get("title") or ""
        return {
            "int_id": row.get("int_id") or row.get("id") or "",
            "agency_id": row.get("agency_id") or "",
            "name": row.get("name") or "",
            "title": title,
            "role": role,
            "agency": row.get("agency") or agency_name,
            "phone": row.get("phone") or row.get("contact_info") or "",
            "email": row.get("email") or "",
            "radio_channel": row.get("radio_channel") or "",
            "preferred_contact": row.get("preferred_contact") or "",
            "notes": row.get("notes") or "",
            "created_at": row.get("created_at") or "",
            "updated_at": row.get("updated_at") or "",
        }

    def _normalize_liaison_interaction(self, row: dict[str, Any], agency_names: dict[Any, str]) -> dict[str, Any]:
        return {
            "int_id": row.get("int_id") or row.get("id") or "",
            "agency_id": row.get("agency_id") or "",
            "agency": agency_names.get(row.get("agency_id"), ""),
            "contact_id": row.get("contact_id") or "",
            "interaction_type": row.get("interaction_type") or "",
            "occurred_at": row.get("occurred_at") or "",
            "subject": row.get("subject") or "",
            "summary": row.get("summary") or "",
            "followup_action": row.get("followup_action") or "",
            "followup_assigned_to": row.get("followup_assigned_to") or "",
            "followup_due": row.get("followup_due") or "",
            "entered_by": row.get("entered_by") or "",
            "created_at": row.get("created_at") or "",
            "updated_at": row.get("updated_at") or "",
            "objective_id": row.get("objective_id") or "",
            "strategy_id": row.get("strategy_id") or "",
            "task_id": row.get("task_id") or "",
            "resource_request_id": row.get("resource_request_id") or "",
        }

    def _normalize_liaison_feedback(self, row: dict[str, Any], agency_names: dict[Any, str]) -> dict[str, Any]:
        return {
            "int_id": row.get("int_id") or row.get("id") or "",
            "agency_id": row.get("agency_id") or "",
            "agency": agency_names.get(row.get("agency_id"), ""),
            "contact_id": row.get("contact_id") or "",
            "feedback_type": row.get("feedback_type") or "",
            "priority": row.get("priority") or "",
            "summary": row.get("summary") or "",
            "requested_action": row.get("requested_action") or "",
            "assigned_section": row.get("assigned_section") or "",
            "assigned_to": row.get("assigned_to") or "",
            "status": row.get("status") or "",
            "interaction_id": row.get("interaction_id") or "",
            "objective_id": row.get("objective_id") or "",
            "strategy_id": row.get("strategy_id") or "",
            "task_id": row.get("task_id") or "",
            "resource_request_id": row.get("resource_request_id") or "",
            "validation_status": row.get("validation_status") or "",
            "followup_due": row.get("followup_due") or "",
            "entered_by": row.get("entered_by") or "",
            "entered_ts": row.get("entered_ts") or "",
            "resolved_by": row.get("resolved_by") or "",
            "resolved_ts": row.get("resolved_ts") or "",
            "resolution_notes": row.get("resolution_notes") or "",
            "created_at": row.get("created_at") or "",
            "updated_at": row.get("updated_at") or "",
        }

    def _normalize_liaison_agency_request(self, row: dict[str, Any], agency_names: dict[Any, str]) -> dict[str, Any]:
        description = row.get("description") or row.get("request_summary") or ""
        due_value = row.get("due_date") or row.get("due_at") or ""
        return {
            "int_id": row.get("int_id") or row.get("id") or "",
            "agency_id": row.get("agency_id") or "",
            "agency": agency_names.get(row.get("agency_id"), ""),
            "contact_id": row.get("contact_id") or "",
            "interaction_id": row.get("interaction_id") or "",
            "description": description,
            "requested_by": row.get("requested_by") or row.get("assigned_to") or "",
            "priority": row.get("priority") or "",
            "status": row.get("status") or "",
            "due_date": due_value,
            "resource_request_id": row.get("resource_request_id") or "",
            "notes": row.get("notes") or "",
            "created_at": row.get("created_at") or "",
            "updated_at": row.get("updated_at") or "",
        }

    def _normalize_liaison_resource_offer(self, row: dict[str, Any], agency_names: dict[Any, str]) -> dict[str, Any]:
        description = row.get("description") or row.get("offer_summary") or ""
        available_from = row.get("available_from") or row.get("availability") or ""
        return {
            "int_id": row.get("int_id") or row.get("id") or "",
            "agency_id": row.get("agency_id") or "",
            "agency": agency_names.get(row.get("agency_id"), ""),
            "contact_id": row.get("contact_id") or "",
            "interaction_id": row.get("interaction_id") or "",
            "description": description,
            "offered_by": row.get("offered_by") or "",
            "quantity": row.get("quantity") or "",
            "available_from": available_from,
            "priority": row.get("priority") or "",
            "status": row.get("status") or "",
            "resource_request_id": row.get("resource_request_id") or "",
            "notes": row.get("notes") or "",
            "created_at": row.get("created_at") or "",
            "updated_at": row.get("updated_at") or "",
        }

    def _normalize_liaison_followup_action(self, row: dict[str, Any], agency_names: dict[Any, str]) -> dict[str, Any]:
        return {
            "int_id": row.get("int_id") or row.get("id") or "",
            "agency_id": row.get("agency_id") or "",
            "agency": agency_names.get(row.get("agency_id"), ""),
            "contact_id": row.get("contact_id") or "",
            "interaction_id": row.get("interaction_id") or "",
            "feedback_id": row.get("feedback_id") or "",
            "action_summary": row.get("action_summary") or row.get("followup_action") or "",
            "assigned_to": row.get("assigned_to") or row.get("followup_assigned_to") or "",
            "due_at": row.get("due_at") or row.get("followup_due") or "",
            "status": row.get("status") or "",
            "objective_id": row.get("objective_id") or "",
            "strategy_id": row.get("strategy_id") or "",
            "task_id": row.get("task_id") or "",
            "resource_request_id": row.get("resource_request_id") or "",
            "created_at": row.get("created_at") or "",
            "updated_at": row.get("updated_at") or "",
        }

    def _normalize_liaison_restriction(self, row: dict[str, Any], agency_names: dict[Any, str]) -> dict[str, Any]:
        return {
            "int_id": row.get("int_id") or row.get("id") or "",
            "agency_id": row.get("agency_id") or "",
            "agency": agency_names.get(row.get("agency_id"), ""),
            "restriction_type": row.get("restriction_type") or "",
            "description": row.get("description") or "",
            "effective_at": row.get("effective_at") or "",
            "expires_at": row.get("expires_at") or "",
            "status": row.get("status") or "",
            "created_at": row.get("created_at") or "",
            "updated_at": row.get("updated_at") or "",
        }

    def _normalize_liaison_agreement(self, row: dict[str, Any], agency_names: dict[Any, str]) -> dict[str, Any]:
        return {
            "int_id": row.get("int_id") or row.get("id") or "",
            "agency_id": row.get("agency_id") or "",
            "agency": agency_names.get(row.get("agency_id"), ""),
            "agreement_type": row.get("agreement_type") or "",
            "description": row.get("description") or "",
            "effective_at": row.get("effective_at") or "",
            "expires_at": row.get("expires_at") or "",
            "status": row.get("status") or "",
            "created_at": row.get("created_at") or "",
            "updated_at": row.get("updated_at") or "",
        }

    # ------------------------------------------------------------------
    # Meetings
    # ------------------------------------------------------------------

    def _build_meetings(self, inc_id: str | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            return _get(f"/api/incidents/{inc_id}/meetings") or []
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Debrief (single record  -  selected at form-generation time)
    # ------------------------------------------------------------------

    _DEBRIEF_TYPE_KEYS = ("ground", "area", "tracking", "hasty", "air_general", "air_sar")

    @classmethod
    def _empty_debrief_shape(cls) -> dict[str, Any]:
        """Default empty shape so debrief.* paths always resolve, even with
        no debrief selected for this form-fill run."""
        shape: dict[str, Any] = {
            "sortie_number": "",
            "debriefer_id": "",
            "status": "",
            "flagged_for_review": False,
            "types": "",
            "created_at": "",
            "updated_at": "",
            "linked_clue_ids": [],
            "linked_subject_ids": [],
            "linked_clues_summary": "",
            "linked_subjects_summary": "",
        }
        for tk in cls._DEBRIEF_TYPE_KEYS:
            shape[tk] = {}
        return shape

    def build_debrief(self, debrief_id: int, incident_id: str | None = None) -> dict[str, Any]:
        """Build the flattened data for a single debrief record, for use as
        ``extra_data={"debrief": ...}`` when generating a debrief-derived form."""
        inc_id = incident_id or incident_context.get_active_incident_id()
        result = self._empty_debrief_shape()
        if not inc_id:
            return result
        try:
            doc = _get(f"/api/incidents/{inc_id}/operations/debriefs/{debrief_id}") or {}
        except Exception:
            doc = {}
        if not doc:
            return result

        result["sortie_number"] = doc.get("sortie_number") or ""
        result["debriefer_id"] = doc.get("debriefer_id") or ""
        result["status"] = doc.get("status") or "Draft"
        result["flagged_for_review"] = bool(doc.get("flagged_for_review"))
        result["types"] = ", ".join(doc.get("types") or [])
        result["created_at"] = doc.get("created_at") or ""
        result["updated_at"] = doc.get("updated_at") or ""

        forms = doc.get("forms") or {}
        for tk in self._DEBRIEF_TYPE_KEYS:
            result[tk] = dict(forms.get(tk) or {})

        clue_ids = list(doc.get("linked_clue_ids") or [])
        subject_ids = list(doc.get("linked_subject_ids") or [])
        result["linked_clue_ids"] = clue_ids
        result["linked_subject_ids"] = subject_ids

        try:
            from modules.intel.repositories.intel_items_repo import IntelItemsRepository
            items_repo = IntelItemsRepository(inc_id)
            titles = []
            for cid in clue_ids:
                item = items_repo.get(cid)
                if item:
                    titles.append(item.title)
            result["linked_clues_summary"] = "; ".join(titles)
        except Exception:
            pass

        try:
            from modules.intel.repositories.subjects_repo import SubjectsRepository
            subjects_repo = SubjectsRepository(inc_id)
            names = []
            for sid in subject_ids:
                s = subjects_repo.get(sid)
                if s:
                    names.append(f"{s.name} ({s.subject_type})")
            result["linked_subjects_summary"] = "; ".join(names)
        except Exception:
            pass

        return result

    # ------------------------------------------------------------------
    # Aircraft (master)
    # ------------------------------------------------------------------

    def _build_aircraft(self) -> list[dict[str, Any]]:
        try:
            return _get("/api/master/aircraft") or []
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Personnel (master)
    # ------------------------------------------------------------------

    def _build_personnel(self) -> list[dict[str, Any]]:
        try:
            return _get("/api/master/personnel") or []
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Vehicles (master)
    # ------------------------------------------------------------------

    def _build_master_vehicles(self) -> list[dict[str, Any]]:
        try:
            return _get("/api/master/vehicles") or []
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Equipment (master)
    # ------------------------------------------------------------------

    def _build_equipment(self) -> list[dict[str, Any]]:
        try:
            return _get("/api/master/equipment") or []
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Comms resources (master)
    # ------------------------------------------------------------------

    def _build_comms_resources(self) -> list[dict[str, Any]]:
        try:
            return _get("/api/comms/channels") or []
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Resource types (master)
    # ------------------------------------------------------------------

    def _build_comm_log(self, inc_id: str | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            rows = _get(f"/api/incidents/{inc_id}/comms-log") or []
            return [
                {
                    "ts_local":            r.get("ts_local") or r.get("ts_utc") or "",
                    "priority":            r.get("priority") or "",
                    "from_unit":           r.get("from_unit") or "",
                    "to_unit":             r.get("to_unit") or "",
                    "frequency":           r.get("frequency") or "",
                    "resource_label":      r.get("resource_label") or "",
                    "message":             r.get("message") or "",
                    "action_taken":        r.get("action_taken") or "",
                    "follow_up_required":  bool(r.get("follow_up_required")),
                    "operator_display_name": r.get("operator_display_name") or "",
                }
                for r in rows
            ]
        except Exception:
            return []

    def _build_resource_types(self) -> list[dict[str, Any]]:
        try:
            return _get("/api/resource-types") or []
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Prepared by
    # ------------------------------------------------------------------

    def _build_prepared_by(self) -> dict[str, Any]:
        now = datetime.now()
        name = position = agency = ""
        try:
            from utils.settingsmanager import SettingsManager
            sm = SettingsManager()
            name     = sm.get("user_name", "")     or ""
            position = sm.get("user_position", "") or ""
            agency   = sm.get("user_agency", "")   or ""
        except Exception:
            pass
        return {
            "name":      name,
            "position":  position,
            "agency":    agency,
            "date_time": now.isoformat(sep=" ", timespec="minutes"),
        }
