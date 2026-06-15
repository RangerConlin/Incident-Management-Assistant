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
        "Incident Commander":             "incident_commander",
        "Deputy Incident Commander":      "deputy_incident_commander",
        "Safety Officer":                 "safety_officer",
        "Public Information Officer":     "public_information_officer",
        "Liaison Officer":                "liaison_officer",
        "Operations Section Chief":       "operations_section_chief",
        "Planning Section Chief":         "planning_section_chief",
        "Logistics Section Chief":        "logistics_section_chief",
        "Finance/Admin Section Chief":    "finance_admin_section_chief",
        "Communications Unit Leader":     "communications_unit_leader",
        "Medical Unit Leader":            "medical_unit_leader",
        "Air Operations Branch Director": "air_operations_branch_director",
        "Ground Support Unit Leader":     "ground_support_unit_leader",
        "Food Unit Leader":               "food_unit_leader",
        "Facilities Unit Leader":         "facilities_unit_leader",
        "Supply Unit Leader":             "supply_unit_leader",
        "Situation Unit Leader":          "situation_unit_leader",
        "Resources Unit Leader":          "resources_unit_leader",
        "Documentation Unit Leader":      "documentation_unit_leader",
        "Demobilization Unit Leader":     "demobilization_unit_leader",
        "Staging Area Manager":           "staging_area_manager",
    }

    def build(self, incident_id: str | None = None) -> dict[str, Any]:
        """Return the full data context dict for the given incident."""
        inc_id = incident_id or incident_context.get_active_incident_id()

        data: dict[str, Any] = {}

        data["incident"]        = self._build_incident(inc_id)
        data["op_period"]       = self._build_op_period(inc_id)
        data["organization"]    = self._build_organization(inc_id)
        data["prepared_by"]     = self._build_prepared_by()

        data["channels"]        = self._build_channels(inc_id)
        data["channels_notes"]  = ""
        data["teams"]           = self._build_teams(inc_id)
        data["tasks"]           = self._build_tasks(inc_id)
        data["objectives"]      = self._build_objectives(inc_id)
        data["vehicles"]        = self._build_incident_vehicles(inc_id)
        data["agency_contacts"] = []
        data["narrative"]       = []
        data["meetings"]        = self._build_meetings(inc_id)
        data["subject"]         = {"name": "", "sex": "", "dob": "", "race": "", "lkp_place": "", "lkp_time": ""}

        data["aircraft"]        = self._build_aircraft()
        data["personnel"]       = self._build_personnel()
        data["master_vehicles"] = self._build_master_vehicles()
        data["equipment"]       = self._build_equipment()
        data["hospitals"]       = []
        data["ems_agencies"]    = []
        data["comms_resources"] = self._build_comms_resources()
        data["resource_types"]  = self._build_resource_types()

        data["message"]         = {}

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
                assignments = _get(f"/api/incidents/{inc_id}/org/assignments") or []
                seen: set[str] = set()
                for row in assignments:
                    title = row.get("position_title") or row.get("title") or ""
                    key = self._ORG_POSITIONS.get(title)
                    if key and key not in seen:
                        result[key] = {
                            "name": row.get("display_name") or row.get("name") or "",
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
            return _get(f"/api/incidents/{inc_id}/tasks") or []
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
