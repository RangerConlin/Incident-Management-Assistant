"""Build a nested data dict for PDF form filling from incident and master databases."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from utils import incident_context, incident_storage


def _conn(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    return dict(row)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone())


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


def _fetch_list(conn: sqlite3.Connection, table: str, columns: str, order: str = "") -> list[dict]:
    if not _table_exists(conn, table):
        return []
    try:
        sql = f"SELECT {columns} FROM {table}"
        if order:
            sql += f" ORDER BY {order}"
        return [dict(r) for r in conn.execute(sql).fetchall()]
    except Exception:
        return []


class FormDataContext:
    """Assemble a nested dict from the active incident and master databases.

    The returned structure matches the dot-notation paths used in mapping.json
    files (e.g. ``incident.name``, ``channels.0.rx_freq``,
    ``organization.incident_commander.name``).
    """

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

        master_path = Path(incident_storage.master_db_path())
        incident_db_path: Path | None = None
        if inc_id:
            paths = incident_storage.resolve_incident_paths_by_identifier(str(inc_id))
            if paths:
                incident_db_path = Path(paths.incident_db)

        data: dict[str, Any] = {}

        # ── Core incident data ───────────────────────────────────────────
        data["incident"]        = self._build_incident(master_path, inc_id)
        data["op_period"]       = self._build_op_period(incident_db_path, inc_id)
        data["organization"]    = self._build_organization(incident_db_path, inc_id)
        data["prepared_by"]     = self._build_prepared_by()

        # ── Incident-DB lists ────────────────────────────────────────────
        data["channels"]        = self._build_channels(incident_db_path)
        data["channels_notes"]  = ""
        data["teams"]           = self._build_teams(incident_db_path)
        data["tasks"]           = self._build_tasks(incident_db_path)
        data["objectives"]      = self._build_objectives(incident_db_path, inc_id)
        data["vehicles"]        = self._build_incident_vehicles(incident_db_path)
        data["agency_contacts"] = self._build_agency_contacts(incident_db_path)
        data["narrative"]       = self._build_narrative(incident_db_path)
        data["meetings"]        = self._build_meetings(incident_db_path)
        data["subject"]         = self._build_subject(incident_db_path)

        # ── Master-DB lists ──────────────────────────────────────────────
        data["aircraft"]        = self._build_aircraft(master_path)
        data["personnel"]       = self._build_personnel(master_path)
        data["master_vehicles"] = self._build_master_vehicles(master_path)
        data["equipment"]       = self._build_equipment(master_path)
        data["hospitals"]       = self._build_hospitals(master_path)
        data["ems_agencies"]    = self._build_ems_agencies(master_path)
        data["comms_resources"] = self._build_comms_resources(master_path)
        data["resource_types"]  = self._build_resource_types(master_path)

        # ── Runtime / per-export ─────────────────────────────────────────
        data["message"]         = {}   # populated at export time for ICS 213

        return data

    # ------------------------------------------------------------------
    # Incident
    # ------------------------------------------------------------------

    def _build_incident(self, master_path: Path, inc_id: str | None) -> dict[str, Any]:
        empty = {"name": "", "number": "", "type": "", "description": "", "icp_location": "", "start_time": ""}
        if not inc_id or not master_path.exists():
            return empty
        try:
            conn = _conn(master_path)
            row = conn.execute(
                "SELECT id, name, number, type, description, icp_location, start_time, end_time "
                "FROM incidents WHERE id=? OR number=? LIMIT 1",
                (inc_id, inc_id),
            ).fetchone()
            conn.close()
            if row:
                return dict(row)
        except Exception:
            pass
        return empty

    # ------------------------------------------------------------------
    # Operational period
    # ------------------------------------------------------------------

    def _build_op_period(self, db_path: Path | None, inc_id: str | None) -> dict[str, Any]:
        empty = {
            "number": "", "start": "", "end": "",
            "start_date": "", "start_time": "", "end_date": "", "end_time": "",
        }
        if not db_path or not db_path.exists():
            return empty
        try:
            conn = _conn(db_path)
            row = None
            if _table_exists(conn, "operationalperiods"):
                row = conn.execute(
                    "SELECT op_number, start_time, end_time "
                    "FROM operationalperiods ORDER BY op_number DESC LIMIT 1"
                ).fetchone()
            if row is None and _table_exists(conn, "iap_packages"):
                row = conn.execute(
                    "SELECT op_number, op_start AS start_time, op_end AS end_time "
                    "FROM iap_packages WHERE incident_id=? ORDER BY op_number DESC LIMIT 1",
                    (str(inc_id),),
                ).fetchone()
            conn.close()
            if row:
                return {
                    "number":     row["op_number"] or "",
                    "start":      row["start_time"] or "",
                    "end":        row["end_time"] or "",
                    "start_date": _fmt_date(row["start_time"]),
                    "start_time": _fmt_time(row["start_time"]),
                    "end_date":   _fmt_date(row["end_time"]),
                    "end_time":   _fmt_time(row["end_time"]),
                }
        except Exception:
            pass
        return empty

    # ------------------------------------------------------------------
    # Organization
    # ------------------------------------------------------------------

    def _build_organization(self, db_path: Path | None, inc_id: str | None) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if not db_path or not db_path.exists():
            return {k: {"name": "", "title": ""} for k in self._ORG_POSITIONS.values()}
        try:
            conn = _conn(db_path)
            rows = conn.execute(
                """
                SELECT op.title, pa.display_name, pa.personnel_id
                FROM position_assignments pa
                JOIN organization_positions op ON pa.position_id = op.id
                WHERE pa.incident_id = ? AND pa.end_time IS NULL
                ORDER BY pa.id DESC
                """,
                (str(inc_id),),
            ).fetchall()
            conn.close()
            seen: set[str] = set()
            for row in rows:
                key = self._ORG_POSITIONS.get(row["title"])
                if key and key not in seen:
                    result[key] = {
                        "name": row["display_name"] or "",
                        "personnel_id": row["personnel_id"] or "",
                        "title": row["title"],
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

    def _build_channels(self, db_path: Path | None) -> list[dict[str, Any]]:
        if not db_path or not db_path.exists():
            return []
        try:
            conn = _conn(db_path)
            if not _table_exists(conn, "incident_channels"):
                conn.close()
                return []
            rows = conn.execute(
                "SELECT channel AS name, function, rx_freq, tx_freq, rx_tone, tx_tone, mode, "
                "assignment_team AS assignment, remarks "
                "FROM incident_channels WHERE include_on_205=1 ORDER BY sort_index, id"
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Teams
    # ------------------------------------------------------------------

    def _build_teams(self, db_path: Path | None) -> list[dict[str, Any]]:
        if not db_path or not db_path.exists():
            return []
        conn = _conn(db_path)
        result = _fetch_list(conn, "teams",
            "id, name, status, leader_name, resource_type", "name")
        conn.close()
        return result

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def _build_tasks(self, db_path: Path | None) -> list[dict[str, Any]]:
        if not db_path or not db_path.exists():
            return []
        conn = _conn(db_path)
        result = _fetch_list(conn, "tasks",
            "id, task_id, title, location, priority, status, assignment, "
            "team_leader, team_phone, radio_primary, radio_alternate, "
            "radio_emergency, category, task_type, due_time", "id")
        conn.close()
        return result

    # ------------------------------------------------------------------
    # Objectives
    # ------------------------------------------------------------------

    def _build_objectives(self, db_path: Path | None, inc_id: str | None) -> list[dict[str, Any]]:
        if not db_path or not db_path.exists():
            return []
        try:
            conn = _conn(db_path)
            if not _table_exists(conn, "incident_objectives"):
                conn.close()
                return []
            rows = conn.execute(
                "SELECT id, description, text, status, priority, assigned_section, "
                "owner_section, due_time, code, display_order "
                "FROM incident_objectives "
                "WHERE (incident_id=? OR incident_id IS NULL) AND status != 'closed' "
                "ORDER BY display_order, id",
                (str(inc_id),),
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Subject (SAR)
    # ------------------------------------------------------------------

    def _build_subject(self, db_path: Path | None) -> dict[str, Any]:
        empty = {"name": "", "sex": "", "dob": "", "race": "", "lkp_place": "", "lkp_time": ""}
        if not db_path or not db_path.exists():
            return empty
        try:
            conn = _conn(db_path)
            if not _table_exists(conn, "subject"):
                conn.close()
                return empty
            row = conn.execute(
                "SELECT name, sex, dob, race, lkp_place, lkp_time FROM subject LIMIT 1"
            ).fetchone()
            conn.close()
            return dict(row) if row else empty
        except Exception:
            return empty

    # ------------------------------------------------------------------
    # Vehicles (incident)
    # ------------------------------------------------------------------

    def _build_incident_vehicles(self, db_path: Path | None) -> list[dict[str, Any]]:
        if not db_path or not db_path.exists():
            return []
        conn = _conn(db_path)
        result = _fetch_list(conn, "vehicles",
            "id, make, model, year, license_plate, capacity, type_id, organization", "id")
        conn.close()
        return result

    # ------------------------------------------------------------------
    # Agency contacts (incident)
    # ------------------------------------------------------------------

    def _build_agency_contacts(self, db_path: Path | None) -> list[dict[str, Any]]:
        if not db_path or not db_path.exists():
            return []
        conn = _conn(db_path)
        result = _fetch_list(conn, "agency_contacts",
            "id, title, name, agency, phone, email, notes", "agency, name")
        conn.close()
        return result

    # ------------------------------------------------------------------
    # Narrative entries
    # ------------------------------------------------------------------

    def _build_narrative(self, db_path: Path | None) -> list[dict[str, Any]]:
        if not db_path or not db_path.exists():
            return []
        conn = _conn(db_path)
        result = _fetch_list(conn, "narrative_entries",
            "id, timestamp, narrative, entered_by, team_num, critical", "timestamp")
        conn.close()
        return result

    # ------------------------------------------------------------------
    # Meetings
    # ------------------------------------------------------------------

    def _build_meetings(self, db_path: Path | None) -> list[dict[str, Any]]:
        if not db_path or not db_path.exists():
            return []
        conn = _conn(db_path)
        result = _fetch_list(conn, "meetings",
            "id, title, meeting_date, start_time, end_time, location, owner, status",
            "meeting_date, start_time")
        conn.close()
        return result

    # ------------------------------------------------------------------
    # Aircraft (master)
    # ------------------------------------------------------------------

    def _build_aircraft(self, master_path: Path) -> list[dict[str, Any]]:
        if not master_path.exists():
            return []
        conn = _conn(master_path)
        result = _fetch_list(conn, "aircraft",
            "id, tail_number, callsign, type, make, model, base, current_location, "
            "status, organization, fuel_type, range_nm, endurance_hr, cruise_kt, "
            "crew_min, crew_max, payload_kg, assigned_team_name", "tail_number")
        conn.close()
        return result

    # ------------------------------------------------------------------
    # Personnel (master)
    # ------------------------------------------------------------------

    def _build_personnel(self, master_path: Path) -> list[dict[str, Any]]:
        if not master_path.exists():
            return []
        conn = _conn(master_path)
        result = _fetch_list(conn, "personnel",
            "id, name, agency, radio_id, certifications", "name")
        conn.close()
        return result

    # ------------------------------------------------------------------
    # Vehicles (master)
    # ------------------------------------------------------------------

    def _build_master_vehicles(self, master_path: Path) -> list[dict[str, Any]]:
        if not master_path.exists():
            return []
        conn = _conn(master_path)
        result = _fetch_list(conn, "vehicles",
            "id, make, model, year, license_plate, capacity, organization", "make, model")
        conn.close()
        return result

    # ------------------------------------------------------------------
    # Equipment (master)
    # ------------------------------------------------------------------

    def _build_equipment(self, master_path: Path) -> list[dict[str, Any]]:
        if not master_path.exists():
            return []
        conn = _conn(master_path)
        result = _fetch_list(conn, "equipment",
            "id, name, type, serial_number, condition, notes", "name")
        conn.close()
        return result

    # ------------------------------------------------------------------
    # Hospitals (master)
    # ------------------------------------------------------------------

    def _build_hospitals(self, master_path: Path) -> list[dict[str, Any]]:
        if not master_path.exists():
            return []
        conn = _conn(master_path)
        result = _fetch_list(conn, "hospitals",
            "id, name, type, phone, fax, address, city, state, zip, contact, notes",
            "name")
        conn.close()
        return result

    # ------------------------------------------------------------------
    # EMS Agencies (master)
    # ------------------------------------------------------------------

    def _build_ems_agencies(self, master_path: Path) -> list[dict[str, Any]]:
        if not master_path.exists():
            return []
        conn = _conn(master_path)
        result = _fetch_list(conn, "ems_agencies",
            "id, name, type, phone, radio_channel, address, city, state, zip, notes",
            "name")
        conn.close()
        return result

    # ------------------------------------------------------------------
    # Comms resources / radio catalog (master)
    # ------------------------------------------------------------------

    def _build_comms_resources(self, master_path: Path) -> list[dict[str, Any]]:
        if not master_path.exists():
            return []
        conn = _conn(master_path)
        result = _fetch_list(conn, "comms_resources",
            "id, alpha_tag, function, freq_rx, rx_tone, freq_tx, tx_tone, system, mode, notes",
            "alpha_tag")
        conn.close()
        return result

    # ------------------------------------------------------------------
    # Resource types (master)
    # ------------------------------------------------------------------

    def _build_resource_types(self, master_path: Path) -> list[dict[str, Any]]:
        if not master_path.exists():
            return []
        conn = _conn(master_path)
        result = _fetch_list(conn, "resource_types",
            "id, name, planning_display_name, category, description, typical_team_size",
            "category, name")
        conn.close()
        return result

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
