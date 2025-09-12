from __future__ import annotations

from typing import Any, Dict, Optional
from datetime import datetime
import os
import sqlite3

from PySide6.QtCore import QObject, Property, Signal, Slot

from utils.styles import team_status_colors, TEAM_TYPE_COLORS, subscribe_theme
from models.database import get_incident_by_number
from utils import incident_context
from utils.state import AppState
from modules.operations.teams.data.team import Team
from modules.operations.teams.data import repository as team_repo
from models.queries import (
    fetch_team_personnel,
    fetch_team_vehicles,
    fetch_team_equipment,
    fetch_team_aircraft,
    fetch_team_leader_id,
    set_person_team,
    set_vehicle_team,
    set_equipment_team,
    set_aircraft_team,
    set_team_leader,
    set_person_role,
    set_team_leader_phone,
    list_available_personnel,
    list_available_aircraft,
    set_person_medic,
)
from utils.app_signals import app_signals
from utils.constants import (
    GT_ROLES,
    UDF_ROLES,
    LSAR_ROLES,
    DF_ROLES,
    UAS_ROLES,
    AIR_ROLES,
    K9_ROLES,
    UTIL_ROLES,
    GT_UAS_ROLES,
    UDF_UAS_ROLES,
)
from utils.constants import TEAM_STATUSES, TEAM_TYPE_DETAILS


class TeamDetailBridge(QObject):
    """Bridge/controller exposed to QML as `teamBridge`.

    Provides a simple property for the team dict and slots for mutating it
    and saving to the active incident database.
    """

    teamChanged = Signal()
    statusChanged = Signal(str)
    error = Signal(str)
    saved = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._team: Team = Team()
        # Cached lists for QML list views
        self._personnel: list[dict[str, Any]] = []
        self._vehicles: list[dict[str, Any]] = []
        self._equipment: list[dict[str, Any]] = []
        self._aircraft: list[dict[str, Any]] = []

        # Display labels mapped to color/status keys used in palette
        overrides = {
            "at other location": "aol",
            "to other location": "tol",
            "rest": "crew rest",
            "returning to base": "returning",
            "post incident management": "post incident",
        }
        self._status_options: list[dict[str, str]] = [
            {
                "label": lbl,
                "key": overrides.get(lbl.lower(), lbl.lower()),
            }
            for lbl in TEAM_STATUSES
        ]

        self._team_type_list: list[dict[str, str]] = [
            {"code": code, "label": info["label"]}
            for code, info in TEAM_TYPE_DETAILS.items()
            if not info.get("planned_only")
        ]
        try:
            subscribe_theme(self, lambda *_: self.statusChanged.emit(self._team.status))
        except Exception:
            pass
        # Refresh assets when signaled elsewhere in the app
        try:
            app_signals.teamAssetsChanged.connect(self._on_assets_changed)
            app_signals.teamLeaderChanged.connect(self._on_leader_changed)
        except Exception:
            pass

    # ---- Properties exposed to QML ----
    @Property('QVariant', notify=teamChanged)
    def team(self) -> Dict[str, Any]:
        return self._team.to_qml()

    @Property('QVariant', constant=True)
    def statusList(self) -> list[dict]:
        return self._status_options

    @Property('QVariant', constant=True)
    def teamTypeList(self) -> list[dict[str, str]]:
        """Return available team type options for the combo box."""
        return self._team_type_list

    @Property(str, notify=teamChanged)
    def teamTypeColor(self) -> str:
        """Color representing the current team type."""
        try:
            code = (self._team.team_type or "").upper()
            color = TEAM_TYPE_COLORS.get(code)
            return color.name() if color else "#5b8efc"
        except Exception:
            return "#5b8efc"

    @Property(bool, notify=teamChanged)
    def isAircraftTeam(self) -> bool:
        code = (self._team.team_type or "").upper()
        info = TEAM_TYPE_DETAILS.get(code)
        return bool(info and info.get("is_aircraft"))

    @Property(bool, notify=teamChanged)
    def needsAssistActive(self) -> bool:
        try:
            return bool(self._team.needs_attention)
        except Exception:
            return False
    @Property('QVariant', notify=statusChanged)
    def teamStatusColor(self) -> Dict[str, str]:
        key = (self._team.status or "").strip().lower()
        st = team_status_colors().get(key)
        try:
            bg = st["bg"].color().name() if st else "#888888"
            fg = st["fg"].color().name() if st else "#000000"
        except Exception:
            bg, fg = "#888888", "#000000"
        return {"bg": bg, "fg": fg}


    # ---- Load/save ----
    @Slot(int)
    def loadTeam(self, team_id: int) -> None:
        try:
            if team_id:
                t = team_repo.get_team(int(team_id))
                self._team = t if t else Team(team_id=int(team_id))
            else:
                self._team = Team()
            # If legacy DB stores leader_id rather than team_leader, fallback
            try:
                if self._team.team_leader_id is None and team_id:
                    lid = fetch_team_leader_id(int(team_id))
                    if lid is not None:
                        self._team.team_leader_id = int(lid)
            except Exception:
                pass
            self._refresh_assets()
            self._auto_set_pilot()
            self.teamChanged.emit()
            self.statusChanged.emit(self._team.status)
        except Exception as e:
            self.error.emit(f"Failed to load team: {e}")

    @Slot()
    def save(self) -> None:
        try:
            # Coordinate validation
            if self._team.last_known_lat is not None:
                lat = float(self._team.last_known_lat)
                if lat < -90 or lat > 90:
                    self.error.emit("Latitude out of bounds (-90..90)")
                    return
            if self._team.last_known_lon is not None:
                lon = float(self._team.last_known_lon)
                if lon < -180 or lon > 180:
                    self.error.emit("Longitude out of bounds (-180..180)")
                    return
            # Placeholder: if current_task_id set, ensure comms preset exists or warn
            # (future: lookup against master db comms_resources)
            self._team.last_update_ts = datetime.utcnow()
            team_repo.save_team(self._team)
            # Notify others (refresh Team Status Panel) via incidentChanged
            try:
                inc = incident_context.get_active_incident_id()
                if inc:
                    from utils.app_signals import app_signals
                    app_signals.incidentChanged.emit(str(inc))
            except Exception:
                pass
            self.saved.emit()
        except Exception as e:
            self.error.emit(f"Failed to save team: {e}")

    # ---- Needs Assistance ----
    @Slot()
    def raiseNeedsAssist(self) -> None:
        """Raise the team's needs-attention flag and persist to DB."""
        try:
            self._team.needs_attention = True
            if self._team.team_id:
                # Persist minimal change quickly
                with team_repo._incident_connect() as con:  # type: ignore[attr-defined]
                    try:
                        con.execute(
                            "UPDATE teams SET needs_attention=? WHERE id=?",
                            (1, int(self._team.team_id)),
                        )
                        con.commit()
                    except Exception:
                        pass
            self.teamChanged.emit()
        except Exception as e:
            self.error.emit(f"Failed to flag needs assistance: {e}")

    # ---- Status ----
    @Slot(str)
    def setStatus(self, new_status: str) -> None:
        try:
            key = (new_status or "").strip()
            # Accept display labels or keys
            for opt in self._status_options:
                if key.lower() == opt["label"].lower():
                    key = opt["key"]
                    break
            self._team.status = key.lower()
            if self._team.team_id:
                team_repo.set_team_status(int(self._team.team_id), self._team.status)
            self.statusChanged.emit(self._team.status)
            # Also request a board refresh
            try:
                inc = incident_context.get_active_incident_id()
                if inc:
                    from utils.app_signals import app_signals
                    app_signals.incidentChanged.emit(str(inc))
            except Exception:
                pass
        except Exception as e:
            self.error.emit(f"Status change failed: {e}")

    @Slot(str)
    def setTeamType(self, code: str) -> None:
        self._team.team_type = str(code)
        self.teamChanged.emit()

    # ---- Asset list providers (QML binds to these) ----
    @Slot(result='QVariant')
    def groundMembers(self) -> list[dict]:
        # Personnel for non-aircraft teams
        out: list[dict[str, Any]] = []
        lid = int(self._team.team_leader_id) if self._team.team_leader_id is not None else None
        for r in self._personnel:
            out.append(
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "role": r.get("role"),
                    "phone": r.get("phone"),
                    "isLeader": (lid is not None and int(r.get("id")) == lid),
                    "isMedic": bool(r.get("is_medic")),
                }
            )
        return out

    @Slot(result='QVariant')
    def aircrewMembers(self) -> list[dict]:
        # For AIR teams show same people, flag PIC as leader and leave certs blank
        out: list[dict[str, Any]] = []
        lid = int(self._team.team_leader_id) if self._team.team_leader_id is not None else None
        for r in self._personnel:
            out.append(
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "role": r.get("role"),
                    "phone": r.get("phone"),
                    "certs": "",  # not modeled in incident db here
                    "isPIC": (lid is not None and int(r.get("id")) == lid),
                }
            )
        return out

    @Slot(result='QVariant')
    def vehicles(self) -> list[dict]:
        out: list[dict[str, Any]] = []
        for r in self._vehicles:
            out.append(
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "callsign": r.get("callsign"),
                    "type": r.get("type"),
                    "driver": "",
                    "phone": "",
                }
            )
        return out

    @Slot(result='QVariant')
    def aircraft(self) -> list[dict]:
        out: list[dict[str, Any]] = []
        for r in self._aircraft:
            out.append(
                {
                    "id": r.get("id"),
                    "tail": r.get("tail_number"),
                    "callsign": r.get("callsign"),
                    "type": r.get("type"),
                    "base": "",
                    "comms": "",
                }
            )
        return out

    @Slot(result='QVariant')
    def availableMembers(self) -> list[dict]:
        try:
            return list_available_personnel() or []
        except Exception:
            return []

    @Slot(result='QVariant')
    def availableAircraft(self) -> list[dict]:
        """Return aircraft available for assignment; include current aircraft if any."""
        try:
            tid = int(self._team.team_id) if self._team.team_id is not None else None
            rows = list_available_aircraft(tid)
            # Normalize labels for QML display
            out: list[dict[str, Any]] = []
            for r in rows:
                label = (r.get("tail_number") or r.get("callsign") or f"#{r.get('id')}")
                out.append({
                    "id": r.get("id"),
                    "label": str(label),
                })
            return out
        except Exception:
            return []

    @Slot(result='QVariant')
    def equipment(self) -> list[dict]:
        out: list[dict[str, Any]] = []
        for r in self._equipment:
            out.append(
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    # Provide additional fields for current QML layout
                    "qty": 1,
                    "notes": f"{r.get('type') or ''} {('('+str(r.get('serial'))+')') if r.get('serial') else ''}".strip(),
                }
            )
        return out

    @Slot(result='QVariant')
    def leaderOptions(self) -> list[dict]:
        try:
            return [
                {"id": r.get("id"), "name": r.get("name")}
                for r in (self._personnel or [])
            ]
        except Exception:
            return []

    @Slot(int, result=str)
    def leaderName(self, person_id: int) -> str:
        try:
            pid = int(person_id) if person_id is not None else None
            if pid is None:
                return ""
            for r in (self._personnel or []):
                try:
                    if int(r.get("id")) == pid:
                        return str(r.get("name") or f"#{pid}")
                except Exception:
                    continue
            return f"#{pid}"
        except Exception:
            return ""

    @Slot(result='QVariant')
    def teamRoleOptions(self) -> list[str]:
        try:
            code = (self._team.team_type or "").upper()
            return {
                "GT": GT_ROLES,
                "UDF": UDF_ROLES,
                "LSAR": LSAR_ROLES,
                "DF": DF_ROLES,
                "UAS": UAS_ROLES,
                "AIR": AIR_ROLES,
                "K9": K9_ROLES,
                "UTIL": UTIL_ROLES,
                "GT/UAS": GT_UAS_ROLES,
                "UDF/UAS": UDF_UAS_ROLES,
            }.get(code, [])
        except Exception:
            return []

    def _refresh_assets(self) -> None:
        try:
            tid = int(self._team.team_id) if self._team.team_id is not None else None
            if not tid:
                self._personnel = []
                self._vehicles = []
                self._equipment = []
                self._aircraft = []
                return
            self._personnel = fetch_team_personnel(tid)
            self._vehicles = fetch_team_vehicles(tid)
            self._equipment = fetch_team_equipment(tid)
            self._aircraft = fetch_team_aircraft(tid)
        except Exception:
            # Keep previous values on error
            pass

    @Slot(int)
    def _on_assets_changed(self, team_id: int) -> None:
        try:
            if self._team.team_id and int(team_id) == int(self._team.team_id):
                # If legacy DB stores leader_id rather than team_leader, fallback
                try:
                    if self._team.team_leader_id is None and team_id:
                        lid = fetch_team_leader_id(int(team_id))
                        if lid is not None:
                            self._team.team_leader_id = int(lid)
                except Exception:
                    pass
                self._refresh_assets()
                self.teamChanged.emit()
        except Exception:
            pass

    @Slot(int)
    def _on_leader_changed(self, team_id: int) -> None:
        try:
            if self._team.team_id and int(team_id) == int(self._team.team_id):
                lid = fetch_team_leader_id(int(team_id))
                self._team.team_leader_id = int(lid) if lid is not None else None
                self.teamChanged.emit()
        except Exception:
            pass
    def _auto_set_pilot(self) -> None:
        """Ensure team_leader_id remains valid and pick a default.

        For aircraft teams, prefer a member whose check-in role contains
        "pilot". For all teams, if the existing leader is missing or no
        suitable pilot is found, fall back to the first member.
        """
        try:
            members = [int(m) for m in self._team.members]
            # Existing leader still valid?
            if self._team.team_leader_id in members:
                return
            self._team.team_leader_id = None
            if not members:
                return
            if self.isAircraftTeam:
                try:
                    from modules.logistics.checkin import repository as checkin_repo
                    for pid in members:
                        rec = checkin_repo.find_personnel_by_id(str(pid))
                        role = (rec.get("role") or "").lower() if rec else ""
                        if "pilot" in role:
                            self._team.team_leader_id = int(pid)
                            break
                except Exception:
                    pass
            if self._team.team_leader_id is None:
                self._team.team_leader_id = members[0]
        except Exception:
            pass

    # ---- Member/asset management ----
    def _is_member_role_valid(self, person_id: int) -> bool:
        """Validate a person's role against the team type.

        Ground teams should not have aircrew and vice versa. The check is
        intentionally lightweight and falls back to True if lookup fails.
        """
        try:
            from modules.logistics.checkin import repository as checkin_repo
            rec = checkin_repo.find_personnel_by_id(str(person_id))
            role = (rec.get("role") or "").lower() if rec else ""
            if self.isAircraftTeam:
                return "air" in role or "pilot" in role
            return not ("air" in role or "pilot" in role)
        except Exception:
            return True

    @Slot('QVariant')
    def addMember(self, person_id: Any = None) -> None:
        """Assign a person to this team by setting their team_id."""
        try:
            if not self._team.team_id:
                raise RuntimeError("No team id")
            if person_id is None:
                # No-op placeholder for UI without selector wired yet
                return
            if not self._is_member_role_valid(int(person_id)):
                self.error.emit("Selected person role not valid for this team")
                return
            set_person_team(int(person_id), int(self._team.team_id))
            app_signals.teamAssetsChanged.emit(int(self._team.team_id))
        except Exception as e:
            self.error.emit(f"Failed to add member: {e}")

    @Slot(int)
    def removeMember(self, person_id: int) -> None:
        """Unassign a person from this team (set team_id = NULL)."""
        try:
            if not self._team.team_id:
                raise RuntimeError("No team id")
            set_person_team(int(person_id), None)
            # Clear leader if removing current leader
            if self._team.team_leader_id == int(person_id):
                set_team_leader(int(self._team.team_id), None)
                self._team.team_leader_id = None
                app_signals.teamLeaderChanged.emit(int(self._team.team_id))
            app_signals.teamAssetsChanged.emit(int(self._team.team_id))
        except Exception as e:
            self.error.emit(f"Failed to remove member: {e}")

    @Slot(int, bool)
    def setMedic(self, person_id: int, is_medic: bool) -> None:
        try:
            set_person_medic(int(person_id), bool(is_medic))
            if self._team.team_id:
                app_signals.teamAssetsChanged.emit(int(self._team.team_id))
        except Exception as e:
            self.error.emit(f"Failed to set medic: {e}")

    @Slot('QVariant')
    def addVehicle(self, vehicle_id: Any) -> None:
        try:
            if not self._team.team_id:
                raise RuntimeError("No team id")
            if vehicle_id is not None and str(vehicle_id) != "":
                set_vehicle_team(int(vehicle_id), int(self._team.team_id))
                app_signals.teamAssetsChanged.emit(int(self._team.team_id))
        except Exception as e:
            self.error.emit(f"Failed to add vehicle: {e}")

    # Convenience for QML unified action in Vehicles/Aircraft tab
    @Slot('QVariant')
    def addAsset(self, asset_id: Any = None) -> None:
        try:
            code = (self._team.team_type or "").upper()
            if code == "AIR":
                self.addAircraft(asset_id)
            else:
                self.addVehicle(asset_id)
        except Exception as e:
            self.error.emit(f"Failed to add asset: {e}")

    @Slot('QVariant')
    def removeVehicle(self, vehicle_id: Any) -> None:
        try:
            if not self._team.team_id:
                raise RuntimeError("No team id")
            set_vehicle_team(int(vehicle_id), None)
            app_signals.teamAssetsChanged.emit(int(self._team.team_id))
        except Exception as e:
            self.error.emit(f"Failed to remove vehicle: {e}")

    # Convenience for QML unified action in Vehicles/Aircraft tab
    @Slot('QVariant')
    def removeAsset(self, asset_id: Any) -> None:
        try:
            code = (self._team.team_type or "").upper()
            if code == "AIR":
                self.removeAircraft(asset_id)
            else:
                self.removeVehicle(asset_id)
        except Exception as e:
            self.error.emit(f"Failed to remove asset: {e}")

    @Slot('QVariant')
    def addEquipment(self, eq_id: Any) -> None:
        try:
            if not self._team.team_id:
                raise RuntimeError("No team id")
            if eq_id is not None and str(eq_id) != "":
                set_equipment_team(int(eq_id), int(self._team.team_id))
                app_signals.teamAssetsChanged.emit(int(self._team.team_id))
        except Exception as e:
            self.error.emit(f"Failed to add equipment: {e}")

    @Slot('QVariant')
    def removeEquipment(self, eq_id: Any) -> None:
        try:
            if not self._team.team_id:
                raise RuntimeError("No team id")
            set_equipment_team(int(eq_id), None)
            app_signals.teamAssetsChanged.emit(int(self._team.team_id))
        except Exception as e:
            self.error.emit(f"Failed to remove equipment: {e}")

    @Slot('QVariant')
    def addAircraft(self, ac_id: Any) -> None:
        try:
            if not self._team.team_id:
                raise RuntimeError("No team id")
            if ac_id is not None and str(ac_id) != "":
                set_aircraft_team(int(ac_id), int(self._team.team_id))
                app_signals.teamAssetsChanged.emit(int(self._team.team_id))
        except Exception as e:
            self.error.emit(f"Failed to add aircraft: {e}")

    @Slot('QVariant')
    def removeAircraft(self, ac_id: Any) -> None:
        try:
            if not self._team.team_id:
                raise RuntimeError("No team id")
            set_aircraft_team(int(ac_id), None)
            app_signals.teamAssetsChanged.emit(int(self._team.team_id))
        except Exception as e:
            self.error.emit(f"Failed to remove aircraft: {e}")

    @Slot('QVariant')
    def setSingleAircraft(self, ac_id: Any) -> None:
        """Ensure only one aircraft is assigned to an AIR team by replacing any existing assignment."""
        try:
            if not self._team.team_id:
                raise RuntimeError("No team id")
            tid = int(self._team.team_id)
            # Detach any currently assigned aircraft first
            for r in (self._aircraft or []):
                try:
                    set_aircraft_team(int(r.get("id")), None)
                except Exception:
                    continue
            if ac_id is not None and str(ac_id) != "":
                set_aircraft_team(int(ac_id), tid)
            app_signals.teamAssetsChanged.emit(tid)
        except Exception as e:
            self.error.emit(f"Failed to set aircraft: {e}")

    @Slot(int)
    def linkTask(self, task_id: int) -> None:
        try:
            self._team.current_task_id = int(task_id)
            self.teamChanged.emit()
        except Exception as e:
            self.error.emit(f"Failed to link task: {e}")

    @Slot(int)
    def unlinkTask(self, task_id: int) -> None:
        try:
            if self._team.current_task_id == int(task_id):
                self._team.current_task_id = None
                self.teamChanged.emit()
        except Exception as e:
            self.error.emit(f"Failed to unlink task: {e}")

    @Slot('QVariant')
    def updateFromQml(self, data: Dict[str, Any]) -> None:
        """Bulk-update primitive fields from QML form bindings."""
        try:
            self._team.name = str(data.get("name", self._team.name or ""))
            self._team.callsign = data.get("callsign") or None
            self._team.role = data.get("role") or None
            self._team.priority = int(data.get("priority")) if data.get("priority") not in (None, "") else None
            self._team.team_leader_id = int(data.get("team_leader_id")) if data.get("team_leader_id") not in (None, "") else None
            self._team.team_type = data.get("team_type", self._team.team_type)
            self._team.primary_task = data.get("primary_task") or None
            self._team.assignment = data.get("assignment") or None
            self._team.team_leader_phone = data.get("team_leader_phone") or None
            self._team.phone = data.get("phone") or None
            self._team.notes = data.get("notes") or None
            lat = data.get("last_known_lat")
            lon = data.get("last_known_lon")
            self._team.last_known_lat = float(lat) if (lat not in (None, "")) else None
            self._team.last_known_lon = float(lon) if (lon not in (None, "")) else None
            self._team.radio_ids = data.get("radio_ids") or None
            self._team.route = data.get("route") or None
            self.teamChanged.emit()
        except Exception as e:
            self.error.emit(f"Invalid input: {e}")

    @Slot('QVariant')
    def openQuickLog(self, template_id: Optional[int] = None) -> None:  # placeholder
        # Future: open Canned Comm Entry dialog
        pass

    @Slot(result='QVariant')
    def unitLog(self) -> list[dict]:
        """Return unit log entries for the team."""
        return []

    @Slot(result='QVariant')
    def taskHistory(self) -> list[dict]:
        """Return task history entries for the team."""
        return []

    @Slot(result='QVariant')
    def statusHistory(self) -> list[dict]:
        """Return status history entries for the team."""
        return []

    @Slot(result='QVariant')
    def ics214Entries(self) -> list[dict]:
        """Return ICS 214 note entries for the team."""
        return []

    @Slot()
    def addIcs214Note(self) -> None:  # placeholder
        """Open dialog to add an ICS 214 note."""
        pass

    @Slot(int)
    def setTeamLeader(self, person_id: int) -> None:
        try:
            if person_id is None:
                return
            if not self._team.team_id:
                raise RuntimeError("No team id")
            # Ensure the leader is assigned to this team
            try:
                set_person_team(int(person_id), int(self._team.team_id))
            except Exception:
                pass
            # Persist leader on team row and refresh badge
            set_team_leader(int(self._team.team_id), int(person_id))
            self._team.team_leader_id = int(person_id)
            try:
                phone = None
                for r in (self._personnel or []):
                    try:
                        if int(r.get('id')) == int(person_id):
                            phone = r.get('phone')
                            break
                    except Exception:
                        continue
                if phone is not None:
                    self._team.team_leader_phone = str(phone)
                    set_team_leader_phone(int(self._team.team_id), str(phone))
            except Exception:
                pass
            self.teamChanged.emit()
            app_signals.teamLeaderChanged.emit(int(self._team.team_id))
            app_signals.teamAssetsChanged.emit(int(self._team.team_id))
            try:
                inc = incident_context.get_active_incident_id()
                if inc:
                    from utils.app_signals import app_signals as _sig
                    _sig.incidentChanged.emit(str(inc))
            except Exception:
                pass
        except Exception as e:
            self.error.emit(f"Failed to set leader: {e}")

    # Alias expected by QML menu
    @Slot(int)
    def setLeader(self, person_id: int) -> None:
        self.setTeamLeader(person_id)

    @Slot(int, str)
    def setPersonRole(self, person_id: int, role: str) -> None:
        try:
            set_person_role(int(person_id), str(role) if role is not None else None)
            # Refresh personnel list
            if self._team.team_id:
                app_signals.teamAssetsChanged.emit(int(self._team.team_id))
        except Exception as e:
            self.error.emit(f"Failed to set role: {e}")

    @Slot()
    def openTaskDetail(self) -> None:
        try:
            tid = self._team.current_task_id
            if not tid:
                self.error.emit("No linked task to open")
                return
            from modules.operations.taskings.windows import open_task_detail_window  # type: ignore
            open_task_detail_window(int(tid))
        except Exception as e:
            self.error.emit(f"Failed to open task detail: {e}")

    @Slot()
    def openICS205Preview(self) -> None:
        # Placeholder: could route to Communications Plan viewer
        pass

    @Slot()
    def printSummary(self) -> None:
        # Placeholder for PDF/HTML export
        pass





