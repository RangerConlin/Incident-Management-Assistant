"""Build a nested data dict for PDF form filling from the SARApp API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from modules.intel.weather.services.summary import build_weather_form_payload
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


def _roman_trauma_level(value: int) -> str:
    return {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}.get(value, "")


def _coerce_trauma_level(value: Any) -> int:
    if value in (None, "", 0, "0", False):
        return 0
    if isinstance(value, int):
        return max(0, min(value, 5))
    text = str(value).strip().upper()
    if text in {"I", "1"}:
        return 1
    if text in {"II", "2"}:
        return 2
    if text in {"III", "3"}:
        return 3
    if text in {"IV", "4"}:
        return 4
    if text in {"V", "5"}:
        return 5
    return 0


def _format_trauma_display(adult_level: int, pediatric_level: int) -> str:
    adult = _roman_trauma_level(adult_level)
    pediatric = _roman_trauma_level(pediatric_level)
    if adult and pediatric:
        return f"A-{adult} / P-{pediatric}"
    if adult:
        return adult
    if pediatric:
        return f"P-{pediatric}"
    return ""


def _coerce_service_level(row: dict[str, Any]) -> int:
    raw = row.get("service_level")
    try:
        if raw not in (None, ""):
            level = int(raw)
            if level in (0, 1, 2):
                return level
    except (TypeError, ValueError):
        pass
    text = str(row.get("type") or "").strip().lower()
    if "als" in text:
        return 2
    if "bls" in text:
        return 1
    return 0


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
        current_op             = self._current_op_number(data["op_period"])
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
        data["narrative"]       = self._build_narrative(inc_id)
        data["meetings"]        = self._build_meetings(inc_id)
        data["subject"]         = {"name": "", "sex": "", "dob": "", "race": "", "lkp_place": "", "lkp_time": ""}
        data["debrief"]         = self._empty_debrief_shape()

        data["aircraft"]        = self._build_aircraft()
        data["personnel"]       = self._build_personnel()
        data["master_vehicles"] = self._build_master_vehicles()
        data["equipment"]       = self._build_equipment()
        data["hospitals"]       = self._build_hospitals()
        data["ems_agencies"]    = self._build_ems_agencies()
        data["ics_206_aid_stations"] = self._build_ics_206_aid_stations(inc_id, current_op)
        data["ics_206_ambulance_services"] = self._build_ics_206_ambulance_services(inc_id, current_op)
        data["ics_206_hospitals"] = self._build_ics_206_hospitals(inc_id, current_op)
        data["ics_206_air_ambulance"] = self._build_ics_206_air_ambulance(inc_id, current_op)
        data["ics_206_medical_comms"] = self._build_ics_206_medical_comms(inc_id, current_op)
        data["ics_206_procedures"] = self._build_ics_206_procedures(inc_id, current_op)
        data["ics_206_signatures"] = self._build_ics_206_signatures(inc_id, current_op)
        data["comms_resources"] = self._build_comms_resources()
        data["resource_types"]  = self._build_resource_types()

        data["message"]         = {}

        data["comm_log"]        = self._build_comm_log(inc_id)
        data["hazards"]         = self._build_hazards(inc_id)
        data["safety_reports"]  = self._build_safety_reports(inc_id)
        data["hazard_zones"]    = self._build_hazard_zones(inc_id)
        data["cap_orm_summaries"] = self._build_cap_orm_summaries(inc_id)
        data["cap_orm_form"]    = self._build_cap_orm_form(inc_id, current_op)
        data["cap_orm_hazards"] = self._build_cap_orm_hazards(inc_id, current_op)
        data["cap_orm_audit"]   = self._build_cap_orm_audit(inc_id, current_op)
        data["ics_208"]         = self._build_ics_208(inc_id, current_op)
        data["ics_215a_rows"]   = self._build_ics_215a_rows(inc_id, current_op)
        data["iwi_reports"]     = self._build_iwi_reports(inc_id)
        data["hazard_types"]    = self._build_hazard_types()
        data["safety_analysis_templates"] = self._build_safety_analysis_templates()
        data["weather"]         = self._build_weather(inc_id)
        data["facilities"]      = self._build_facilities(inc_id)

        data["uc_commanders"]              = self._build_uc_commanders(inc_id)
        data["org_branches"]               = self._build_org_branches(inc_id)   # each entry carries branch director + div slots
        data["org_agency_reps"]            = liaison_data["agency_contacts"]
        data["team_members"]               = []
        data["planning_tech_specialists"]  = self._build_planning_tech_specialists(inc_id)

        return data

    @staticmethod
    def _current_op_number(op_period: dict[str, Any]) -> int | None:
        raw = op_period.get("number")
        if raw in (None, ""):
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Incident
    # ------------------------------------------------------------------

    def _build_incident(self, inc_id: str | None) -> dict[str, Any]:
        empty = {
            "name": "",
            "number": "",
            "type": "",
            "description": "",
            "icp_location": "",
            "icp_facility_id": "",
            "icp_facility_name": "",
            "start_time": "",
        }
        if not inc_id:
            return empty
        try:
            doc = _get(f"/api/incidents/{inc_id}")
            if doc:
                icp_facility_id = str(doc.get("icp_facility_id") or "")
                icp_facility_name = ""
                if icp_facility_id:
                    try:
                        facility = _get(f"/api/incidents/{inc_id}/facilities/{icp_facility_id}") or {}
                        icp_facility_name = str(facility.get("name") or "")
                    except Exception:
                        icp_facility_name = ""
                return {
                    "id": doc.get("id", ""),
                    "name": doc.get("name", ""),
                    "number": doc.get("number", "") or doc.get("incident_number", ""),
                    "type": doc.get("type", "") or doc.get("incident_type", ""),
                    "description": doc.get("description", ""),
                    "icp_location": doc.get("icp_location", "") or doc.get("location", ""),
                    "icp_facility_id": icp_facility_id,
                    "icp_facility_name": icp_facility_name,
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
            periods = _get(f"/api/incidents/{inc_id}/planning/operational-periods") or []
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
            rows = _get(f"/api/incidents/{inc_id}/channels-plan") or []
            return [
                {
                    "id": r.get("id") or "",
                    "channel_id": r.get("channel_id") or "",
                    "master_id": r.get("master_id") or "",
                    "channel": r.get("channel") or r.get("name") or "",
                    "name": r.get("channel") or r.get("name") or "",
                    "function": r.get("function") or "",
                    "band": r.get("band") or "",
                    "system": r.get("system") or "",
                    "system_type": r.get("system") or "",
                    "rx_freq": r.get("rx_freq") or r.get("freq_rx") or "",
                    "tx_freq": r.get("tx_freq") or r.get("freq_tx") or "",
                    "rx_tone": r.get("rx_tone") or "",
                    "tx_tone": r.get("tx_tone") or "",
                    "encryption": r.get("encryption") or "",
                    "assignment_division": r.get("assignment_division") or "",
                    "assignment_team": r.get("assignment_team") or "",
                    "priority": r.get("priority") or "",
                    "include_on_205": bool(r.get("include_on_205", True)),
                    "sort_index": r.get("sort_index") or "",
                    "line_a": bool(r.get("line_a")),
                    "line_c": bool(r.get("line_c")),
                    "created_at": r.get("created_at") or "",
                    "updated_at": r.get("updated_at") or "",
                    "mode": r.get("mode") or "",
                    "assignment": (
                        r.get("assignment")
                        or r.get("assignment_team")
                        or r.get("assignment_division")
                        or ""
                    ),
                    "remarks": r.get("remarks") or r.get("notes") or "",
                }
                for r in rows
            ]
        except Exception:
            return []

    def _build_narrative(self, inc_id: str | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            streams = _get(f"/api/incidents/{inc_id}/ics214/streams") or []
            entries: list[dict[str, Any]] = []
            for stream in streams:
                stream_id = stream.get("id")
                if not stream_id:
                    continue
                detail = _get(f"/api/incidents/{inc_id}/ics214/streams/{stream_id}") or {}
                stream_name = detail.get("name") or stream.get("name") or ""
                stream_entries = detail.get("entries") or []
                for entry in stream_entries:
                    entries.append(
                        {
                            "id": entry.get("id") or "",
                            "stream_id": entry.get("stream_id") or stream_id,
                            "timestamp": entry.get("timestamp_utc") or "",
                            "timestamp_utc": entry.get("timestamp_utc") or "",
                            "narrative": entry.get("text") or "",
                            "text": entry.get("text") or "",
                            "entered_by": entry.get("actor_user_id") or "",
                            "actor_user_id": entry.get("actor_user_id") or "",
                            "team_num": self._extract_team_num(stream_name),
                            "stream_name": stream_name,
                            "source": entry.get("source") or "",
                            "autogenerated": bool(entry.get("autogenerated")),
                            "critical": bool(entry.get("critical_flag")),
                            "critical_flag": bool(entry.get("critical_flag")),
                            "idempotency_hash": entry.get("idempotency_hash") or "",
                            "tags": entry.get("tags") or [],
                        }
                    )
            entries.sort(key=lambda item: item.get("timestamp_utc") or item.get("timestamp") or "")
            return entries
        except Exception:
            return []

    @staticmethod
    def _extract_team_num(value: str) -> str:
        if not value:
            return ""
        upper = value.upper()
        for marker in ("TEAM-", "TEAM ", "T-"):
            if marker not in upper:
                continue
            tail = upper.split(marker, 1)[1]
            digits = "".join(ch for ch in tail if ch.isdigit())
            if digits:
                return digits
        return ""

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
                r.setdefault("location_facility_id", r.get("location_facility_id") or "")
            return rows
        except Exception:
            return []

    def _build_facilities(self, inc_id: str | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            rows = _get(f"/api/incidents/{inc_id}/facilities") or []
            return [
                {
                    "id": row.get("id") or "",
                    "incident_id": row.get("incident_id") or inc_id,
                    "name": row.get("name") or "",
                    "facility_type": row.get("facility_type") or "",
                    "status": row.get("status") or "",
                    "address": row.get("address") or "",
                    "geocoded_address": row.get("geocoded_address") or "",
                    "latitude": row.get("latitude"),
                    "longitude": row.get("longitude"),
                    "manager_personnel_id": row.get("manager_personnel_id") or "",
                    "manager_name": row.get("manager_name") or "",
                    "contact_name": row.get("contact_name") or "",
                    "contact_phone": row.get("contact_phone") or "",
                    "notes": row.get("notes") or "",
                    "is_primary": bool(row.get("is_primary")),
                }
                for row in rows
            ]
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

    def _build_hazards(self, inc_id: str | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            snapshot = _get(f"/api/incidents/{inc_id}/snapshot", collections="hazards") or {}
            rows = ((snapshot.get("collections") or {}).get("hazards")) or []
            return [
                {
                    "id": row.get("id") or "",
                    "incident_id": row.get("incident_id") or "",
                    "work_assignment_id": row.get("work_assignment_id") or row.get("strategy_id") or "",
                    "hazard_type_id": row.get("hazard_type_id") or "",
                    "hazard_type_text": row.get("hazard_type_text") or row.get("name") or "",
                    "risk_level": row.get("risk_level") or "",
                    "likelihood": row.get("likelihood") or "",
                    "severity": row.get("severity") or "",
                    "control_measure": row.get("control_measure") or "",
                    "mitigation_text": row.get("mitigation_text") or "",
                    "ppe_text": row.get("ppe_text") or "",
                    "safety_message": row.get("safety_message") or "",
                    "is_resolved": bool(row.get("is_resolved")),
                    "notes": row.get("notes") or "",
                    "created_at": row.get("created_at") or "",
                    "updated_at": row.get("updated_at") or "",
                }
                for row in rows
            ]
        except Exception:
            return []

    def _build_safety_reports(self, inc_id: str | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            rows = _get(f"/api/incidents/{inc_id}/safety/reports") or []
            return [
                {
                    "id": row.get("id") or "",
                    "incident_id": row.get("incident_id") or "",
                    "time": row.get("time") or "",
                    "location": row.get("location") or "",
                    "severity": row.get("severity") or "",
                    "notes": row.get("notes") or "",
                    "flagged": bool(row.get("flagged")),
                    "reported_by": row.get("reported_by") or "",
                    "team_id": row.get("team_id") or "",
                    "created_at": row.get("created_at") or "",
                    "updated_at": row.get("updated_at") or "",
                }
                for row in rows
            ]
        except Exception:
            return []

    def _build_hazard_zones(self, inc_id: str | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            rows = _get(f"/api/incidents/{inc_id}/safety/zones") or []
            return [
                {
                    "id": row.get("id") or "",
                    "incident_id": row.get("incident_id") or "",
                    "name": row.get("name") or "",
                    "coordinates_json": row.get("coordinates_json") or "",
                    "severity": row.get("severity") or "",
                    "description": row.get("description") or "",
                    "created_at": row.get("created_at") or "",
                    "updated_at": row.get("updated_at") or "",
                }
                for row in rows
            ]
        except Exception:
            return []

    def _build_cap_orm_summaries(self, inc_id: str | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            snapshot = _get(f"/api/incidents/{inc_id}/snapshot", collections="cap_orm_summaries") or {}
            rows = ((snapshot.get("collections") or {}).get("cap_orm_summaries")) or []
            return [
                {
                    "id": row.get("id") or "",
                    "incident_id": row.get("incident_id") or "",
                    "form_type": row.get("form_type") or "",
                    "activity": row.get("activity") or "",
                    "participants_json": row.get("participants_json") or "",
                    "hazards_json": row.get("hazards_json") or "",
                    "mitigations_json": row.get("mitigations_json") or "",
                    "residual_risk": row.get("residual_risk") or "",
                    "created_by": row.get("created_by") or "",
                    "created_at": row.get("created_at") or "",
                    "updated_at": row.get("updated_at") or "",
                }
                for row in rows
            ]
        except Exception:
            return []

    def _build_cap_orm_form(self, inc_id: str | None, op_number: int | None) -> dict[str, Any]:
        empty = {
            "id": "", "incident_id": "", "op_period": "", "activity": "", "prepared_by_id": "",
            "date_iso": "", "highest_residual_risk": "", "status": "", "approval_blocked": False,
            "created_at": "", "updated_at": "",
        }
        if not inc_id or op_number is None:
            return empty
        try:
            row = _get(f"/api/incidents/{inc_id}/safety/orm/form", op=op_number) or {}
            if not row:
                return empty
            return {
                "id": row.get("id") or "",
                "incident_id": row.get("incident_id") or "",
                "op_period": row.get("op_period") or op_number,
                "activity": row.get("activity") or "",
                "prepared_by_id": row.get("prepared_by_id") or "",
                "date_iso": row.get("date_iso") or "",
                "highest_residual_risk": row.get("highest_residual_risk") or "",
                "status": row.get("status") or "",
                "approval_blocked": bool(row.get("approval_blocked")),
                "created_at": row.get("created_at") or "",
                "updated_at": row.get("updated_at") or "",
            }
        except Exception:
            return empty

    def _build_cap_orm_hazards(self, inc_id: str | None, op_number: int | None) -> list[dict[str, Any]]:
        if not inc_id or op_number is None:
            return []
        try:
            rows = _get(f"/api/incidents/{inc_id}/safety/orm/hazards", op=op_number) or []
            return [
                {
                    "id": row.get("id") or "",
                    "form_id": row.get("form_id") or "",
                    "sub_activity": row.get("sub_activity") or "",
                    "hazard_outcome": row.get("hazard_outcome") or "",
                    "initial_risk": row.get("initial_risk") or "",
                    "control_text": row.get("control_text") or "",
                    "residual_risk": row.get("residual_risk") or "",
                    "implement_how": row.get("implement_how") or "",
                    "implement_who": row.get("implement_who") or "",
                    "created_at": row.get("created_at") or "",
                    "updated_at": row.get("updated_at") or "",
                }
                for row in rows
            ]
        except Exception:
            return []

    def _build_cap_orm_audit(self, inc_id: str | None, op_number: int | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            snapshot = _get(f"/api/incidents/{inc_id}/snapshot", collections="cap_orm_audit") or {}
            rows = ((snapshot.get("collections") or {}).get("cap_orm_audit")) or []
            if op_number is not None:
                form = self._build_cap_orm_form(inc_id, op_number)
                form_id = form.get("id")
                rows = [row for row in rows if not form_id or row.get("entity_id") in {form_id, int(form_id) if str(form_id).isdigit() else form_id}]
            return [
                {
                    "incident_id": row.get("incident_id") or "",
                    "entity": row.get("entity") or "",
                    "entity_id": row.get("entity_id") or "",
                    "action": row.get("action") or "",
                    "field": row.get("field") or "",
                    "old_value": row.get("old_value") or "",
                    "new_value": row.get("new_value") or "",
                    "ts_iso": row.get("ts_iso") or "",
                }
                for row in rows
            ]
        except Exception:
            return []

    def _build_ics_208(self, inc_id: str | None, op_number: int | None) -> dict[str, Any]:
        empty = {
            "incident_id": "", "op_period": "", "op_period_from": "", "op_period_to": "",
            "safety_message": "", "site_safety_plan_required": False, "site_safety_plan_location": "",
            "weather_summary": "",
            "prepared_by_name": "", "prepared_by_position": "", "prepared_by_datetime": "",
            "created_at": "", "updated_at": "",
        }
        if not inc_id or op_number is None:
            return empty
        try:
            row = _get(f"/api/incidents/{inc_id}/safety/ics208", op=op_number) or {}
            if not row:
                return empty
            return {
                "incident_id": row.get("incident_id") or inc_id,
                "op_period": row.get("op_period") or op_number,
                "op_period_from": row.get("op_period_from") or "",
                "op_period_to": row.get("op_period_to") or "",
                "safety_message": row.get("safety_message") or "",
                "site_safety_plan_required": bool(row.get("site_safety_plan_required")),
                "site_safety_plan_location": row.get("site_safety_plan_location") or "",
                "weather_summary": row.get("weather_summary") or "",
                "prepared_by_name": row.get("prepared_by_name") or "",
                "prepared_by_position": row.get("prepared_by_position") or "",
                "prepared_by_datetime": row.get("prepared_by_datetime") or "",
                "created_at": row.get("created_at") or "",
                "updated_at": row.get("updated_at") or "",
            }
        except Exception:
            return empty

    def _build_weather(self, inc_id: str | None) -> dict[str, Any]:
        if not inc_id:
            return build_weather_form_payload({})
        try:
            config = _get(f"/api/incidents/{inc_id}/weather") or {}
        except Exception:
            config = {}
        return build_weather_form_payload(config)

    def _build_iwi_reports(self, inc_id: str | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            rows = _get(f"/api/incidents/{inc_id}/safety/iwi") or []
            return [
                {
                    "id": row.get("id") or "",
                    "form_number": row.get("form_number") or "",
                    "incident_id": row.get("incident_id") or "",
                    "status": row.get("status") or "",
                    "op_period": row.get("op_period") or "",
                    "date_of_occurrence": row.get("date_of_occurrence") or "",
                    "day_of_event": row.get("day_of_event") or "",
                    "time_of_occurrence": row.get("time_of_occurrence") or "",
                    "time_reported": row.get("time_reported") or "",
                    "reported_by": row.get("reported_by") or "",
                    "location_general": row.get("location_general") or "",
                    "location_zone": row.get("location_zone") or "",
                    "location_sector": row.get("location_sector") or "",
                    "location_specific": row.get("location_specific") or "",
                    "incident_types": row.get("incident_types") or [],
                    "incident_type_other": row.get("incident_type_other") or "",
                    "actual_outcome": row.get("actual_outcome") or "",
                    "actual_severity": row.get("actual_severity") or "",
                    "activity_impact": row.get("activity_impact") or "",
                    "activity_suspension_ref": row.get("activity_suspension_ref") or "",
                    "conditions": row.get("conditions") or {},
                    "persons_involved": row.get("persons_involved") or [],
                    "injury_details": row.get("injury_details") or [],
                    "equipment": row.get("equipment") or {},
                    "sequence_of_events": row.get("sequence_of_events") or [],
                    "narrative": row.get("narrative") or "",
                    "contributing_factors": row.get("contributing_factors") or {},
                    "immediate_actions": row.get("immediate_actions") or "",
                    "notifications": row.get("notifications") or [],
                    "corrective_actions": row.get("corrective_actions") or [],
                    "escalation_decision": row.get("escalation_decision") or "",
                    "escalation_rationale": row.get("escalation_rationale") or "",
                    "witnesses": row.get("witnesses") or [],
                    "prepared_by": row.get("prepared_by") or "",
                    "signoffs": row.get("signoffs") or {},
                    "created_at": row.get("created_at") or "",
                    "updated_at": row.get("updated_at") or "",
                }
                for row in rows
            ]
        except Exception:
            return []

    def _build_ics_215a_rows(self, inc_id: str | None, op_number: int | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            params: dict[str, Any] = {}
            if op_number is not None:
                params["op_period_id"] = op_number
            work_assignments = _get(
                f"/api/incidents/{inc_id}/planning/work-assignments",
                **params,
            ) or []
            rows: list[dict[str, Any]] = []
            for assignment in work_assignments:
                branch = assignment.get("branch") or ""
                division_group = assignment.get("division_group") or ""
                assignment_number = assignment.get("assignment_number") or ""
                assignment_name = assignment.get("assignment_name") or ""
                branch_div_group = " / ".join(
                    part for part in (branch, division_group) if part
                )
                if not branch_div_group:
                    branch_div_group = assignment_number or assignment_name
                work_assignment = " - ".join(
                    part for part in (assignment_number, assignment_name) if part
                ) or assignment_name or assignment_number
                for hazard in assignment.get("hazards") or []:
                    rows.append(
                        {
                            "work_assignment_id": assignment.get("id") or "",
                            "branch_div_group": branch_div_group,
                            "work_assignment": work_assignment,
                            "assignment_number": assignment_number,
                            "assignment_name": assignment_name,
                            "location": assignment.get("location") or "",
                            "location_facility_id": assignment.get("location_facility_id") or "",
                            "hazard_id": hazard.get("id") or "",
                            "hazard": hazard.get("hazard_type_text") or "",
                            "category": hazard.get("category") or "",
                            "risk_level": hazard.get("risk_level") or "",
                            "likelihood": hazard.get("likelihood") or "",
                            "severity": hazard.get("severity") or "",
                            "control_measure": hazard.get("control_measure")
                            or hazard.get("mitigation_text")
                            or "",
                            "mitigation_text": hazard.get("mitigation_text") or "",
                            "ppe_text": hazard.get("ppe_text") or "",
                            "resolved": bool(hazard.get("is_resolved")),
                            "notes": hazard.get("notes") or "",
                        }
                    )
            return rows
        except Exception:
            return []

    def _build_hazard_types(self) -> list[dict[str, Any]]:
        try:
            rows = _get("/api/hazard-types") or []
            return [
                {
                    "id": row.get("id") or "",
                    "hazard_type_id": row.get("hazard_type_id") or "",
                    "name": row.get("name") or "",
                    "display_name": row.get("display_name") or "",
                    "category": row.get("category") or "",
                    "source": row.get("source") or "",
                    "owner_agency": row.get("owner_agency") or "",
                    "description": row.get("description") or "",
                    "default_risk_level": row.get("default_risk_level") or "",
                    "default_likelihood": row.get("default_likelihood") or "",
                    "default_severity": row.get("default_severity") or "",
                    "default_control_measure": row.get("default_control_measure") or "",
                    "default_ppe": row.get("default_ppe") or "",
                    "default_safety_message": row.get("default_safety_message") or "",
                    "is_active": bool(row.get("is_active", True)),
                    "notes": row.get("notes") or "",
                    "created_by": row.get("created_by") or "",
                    "updated_by": row.get("updated_by") or "",
                    "aliases": row.get("aliases") or [],
                    "mitigations": row.get("mitigations") or [],
                    "ppe_items": row.get("ppe_items") or [],
                    "references": row.get("references") or [],
                    "resource_defaults": row.get("resource_defaults") or [],
                    "mitigation_count": row.get("mitigation_count") or 0,
                    "ppe_preview": row.get("ppe_preview") or "",
                    "created_at": row.get("created_at") or "",
                    "updated_at": row.get("updated_at") or "",
                }
                for row in rows
            ]
        except Exception:
            return []

    def _build_safety_analysis_templates(self) -> list[dict[str, Any]]:
        try:
            rows = _get("/api/master/safety-templates") or []
            return [
                {
                    "template_id": row.get("template_id") or "",
                    "name": row.get("name") or "",
                    "description": row.get("description") or "",
                    "scenario_type": row.get("scenario_type") or "",
                    "target_forms": row.get("target_forms") or [],
                    "hazard_entries": row.get("hazard_entries") or [],
                    "is_active": bool(row.get("is_active", True)),
                    "notes": row.get("notes") or "",
                    "created_by": row.get("created_by") or "",
                    "updated_by": row.get("updated_by") or "",
                    "created_at": row.get("created_at") or "",
                    "updated_at": row.get("updated_at") or "",
                }
                for row in rows
            ]
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
    # Medical (master + incident ICS 206)
    # ------------------------------------------------------------------

    def _normalize_hospital_row(self, row: dict[str, Any]) -> dict[str, Any]:
        adult_level = _coerce_trauma_level(
            row.get("adult_trauma_level") or row.get("trauma_level") or row.get("level")
        )
        pediatric_level = _coerce_trauma_level(row.get("pediatric_trauma_level"))
        if pediatric_level == 0 and row.get("pediatric_capability") and adult_level:
            pediatric_level = adult_level
        return {
            "id": row.get("id") or "",
            "hospital_id": row.get("hospital_id") or "",
            "name": row.get("name") or "",
            "type": row.get("type") or "",
            "code": row.get("code") or "",
            "phone": row.get("phone") or "",
            "phone_er": row.get("phone_er") or "",
            "phone_switchboard": row.get("phone_switchboard") or "",
            "fax": row.get("fax") or "",
            "email": row.get("email") or "",
            "address": row.get("address") or "",
            "city": row.get("city") or "",
            "state": row.get("state") or "",
            "zip": row.get("zip") or "",
            "contact": row.get("contact") or "",
            "contact_name": row.get("contact_name") or "",
            "helipad": bool(row.get("helipad")),
            "burn_center": bool(row.get("burn_center")),
            "pediatric_capability": bool(row.get("pediatric_capability")),
            "adult_trauma_level": adult_level,
            "pediatric_trauma_level": pediatric_level,
            "trauma_level_display": _format_trauma_display(adult_level, pediatric_level),
            "travel_time_min": row.get("travel_time_min") or "",
            "bed_available": row.get("bed_available") or "",
            "diversion_status": row.get("diversion_status") or "",
            "ambulance_radio_channel": row.get("ambulance_radio_channel") or "",
            "lat": row.get("lat") if row.get("lat") is not None else "",
            "lon": row.get("lon") if row.get("lon") is not None else "",
            "notes": row.get("notes") or "",
            "is_active": bool(row.get("is_active", True)),
            "op_period": row.get("op_period") or "",
        }

    def _normalize_ems_agency_row(self, row: dict[str, Any]) -> dict[str, Any]:
        service_level = _coerce_service_level(row)
        return {
            "id": row.get("id") or "",
            "name": row.get("name") or "",
            "type": row.get("type") or "",
            "service_level": service_level,
            "service_level_label": {0: "Other", 1: "BLS", 2: "ALS"}.get(service_level, "Other"),
            "phone": row.get("phone") or "",
            "radio_channel": row.get("radio_channel") or "",
            "address": row.get("address") or "",
            "city": row.get("city") or "",
            "state": row.get("state") or "",
            "zip": row.get("zip") or "",
            "lat": row.get("lat") if row.get("lat") is not None else "",
            "lon": row.get("lon") if row.get("lon") is not None else "",
            "notes": row.get("notes") or "",
            "default_on_206": bool(row.get("default_on_206")),
            "is_active": bool(row.get("is_active", True)),
            "op_period": row.get("op_period") or "",
        }

    def _build_hospitals(self) -> list[dict[str, Any]]:
        try:
            rows = _get("/api/master/hospitals") or []
            return [self._normalize_hospital_row(row) for row in rows]
        except Exception:
            return []

    def _build_ems_agencies(self) -> list[dict[str, Any]]:
        try:
            rows = _get("/api/master/ems-agencies") or []
            return [self._normalize_ems_agency_row(row) for row in rows]
        except Exception:
            return []

    def _build_ics_206_aid_stations(self, inc_id: str | None, op_number: int | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            rows = _get(f"/api/incidents/{inc_id}/medical/ics206/aid-stations", op=op_number) or []
            return [
                {
                    "id": row.get("id") or "",
                    "op_period": row.get("op_period") or "",
                    "name": row.get("name") or "",
                    "type": row.get("type") or "",
                    "level": row.get("level") or "",
                    "facility_id": row.get("facility_id") or "",
                    "location_text": row.get("location_text") or "",
                    "latitude": row.get("latitude"),
                    "longitude": row.get("longitude"),
                    "is_24_7": bool(row.get("is_24_7")),
                    "notes": row.get("notes") or "",
                }
                for row in rows
            ]
        except Exception:
            return []

    def _build_ics_206_ambulance_services(self, inc_id: str | None, op_number: int | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            rows = _get(f"/api/incidents/{inc_id}/medical/ics206/ambulance-services", op=op_number) or []
            return [
                {
                    "id": row.get("id") or "",
                    "op_period": row.get("op_period") or "",
                    "name": row.get("name") or "",
                    "type": row.get("type") or "",
                    "service_level": _coerce_service_level(row),
                    "service_level_label": {0: "Other", 1: "BLS", 2: "ALS"}.get(_coerce_service_level(row), "Other"),
                    "phone": row.get("phone") or "",
                    "location": row.get("location") or "",
                    "notes": row.get("notes") or "",
                }
                for row in rows
            ]
        except Exception:
            return []

    def _build_ics_206_hospitals(self, inc_id: str | None, op_number: int | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            rows = _get(f"/api/incidents/{inc_id}/medical/ics206/hospitals", op=op_number) or []
            return [self._normalize_hospital_row(row) for row in rows]
        except Exception:
            return []

    def _build_ics_206_air_ambulance(self, inc_id: str | None, op_number: int | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            rows = _get(f"/api/incidents/{inc_id}/medical/ics206/air-ambulance", op=op_number) or []
            return [
                {
                    "id": row.get("id") or "",
                    "op_period": row.get("op_period") or "",
                    "name": row.get("name") or "",
                    "phone": row.get("phone") or "",
                    "base": row.get("base") or "",
                    "contact": row.get("contact") or "",
                    "notes": row.get("notes") or "",
                }
                for row in rows
            ]
        except Exception:
            return []

    def _build_ics_206_medical_comms(self, inc_id: str | None, op_number: int | None) -> list[dict[str, Any]]:
        if not inc_id:
            return []
        try:
            rows = _get(f"/api/incidents/{inc_id}/medical/ics206/comms", op=op_number) or []
            return [
                {
                    "id": row.get("id") or "",
                    "op_period": row.get("op_period") or "",
                    "channel": row.get("channel") or "",
                    "function": row.get("function") or "",
                    "frequency": row.get("frequency") or "",
                    "mode": row.get("mode") or "",
                    "notes": row.get("notes") or "",
                }
                for row in rows
            ]
        except Exception:
            return []

    def _build_ics_206_procedures(self, inc_id: str | None, op_number: int | None) -> dict[str, Any]:
        empty = {"id": "", "op_period": "", "content": ""}
        if not inc_id:
            return empty
        try:
            row = _get(f"/api/incidents/{inc_id}/medical/ics206/procedures", op=op_number) or {}
            if not row:
                return empty
            return {
                "id": row.get("id") or "",
                "op_period": row.get("op_period") or "",
                "content": row.get("content") or "",
            }
        except Exception:
            return empty

    def _build_ics_206_signatures(self, inc_id: str | None, op_number: int | None) -> dict[str, Any]:
        empty = {
            "id": "", "op_period": "", "prepared_by": "", "position": "",
            "approved_by": "", "date": "",
        }
        if not inc_id:
            return empty
        try:
            row = _get(f"/api/incidents/{inc_id}/medical/ics206/signatures", op=op_number) or {}
            if not row:
                return empty
            return {
                "id": row.get("id") or "",
                "op_period": row.get("op_period") or "",
                "prepared_by": row.get("prepared_by") or "",
                "position": row.get("position") or "",
                "approved_by": row.get("approved_by") or "",
                "date": row.get("date") or "",
            }
        except Exception:
            return empty

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
                    "id": r.get("id") or "",
                    "comms_id": r.get("comms_id") or "",
                    "ts_utc": r.get("ts_utc") or "",
                    "ts_local":            r.get("ts_local") or r.get("ts_utc") or "",
                    "direction":           r.get("direction") or "",
                    "priority":            r.get("priority") or "",
                    "resource_id":         r.get("resource_id") or "",
                    "from_unit":           r.get("from_unit") or "",
                    "to_unit":             r.get("to_unit") or "",
                    "frequency":           r.get("frequency") or "",
                    "band":                r.get("band") or "",
                    "mode":                r.get("mode") or "",
                    "resource_label":      r.get("resource_label") or "",
                    "message":             r.get("message") or "",
                    "action_taken":        r.get("action_taken") or "",
                    "follow_up_required":  bool(r.get("follow_up_required")),
                    "disposition":         r.get("disposition") or "",
                    "operator_user_id":    r.get("operator_user_id") or "",
                    "operator_display_name": r.get("operator_display_name") or "",
                    "team_id":             r.get("team_id") or "",
                    "task_id":             r.get("task_id") or "",
                    "vehicle_id":          r.get("vehicle_id") or "",
                    "personnel_id":        r.get("personnel_id") or "",
                    "attachments":         r.get("attachments") or [],
                    "geotag_lat":          r.get("geotag_lat"),
                    "geotag_lon":          r.get("geotag_lon"),
                    "notification_level":  r.get("notification_level") or "",
                    "is_status_update":    bool(r.get("is_status_update")),
                    "created_at":          r.get("created_at") or "",
                    "updated_at":          r.get("updated_at") or "",
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
