from __future__ import annotations

from typing import Any, Dict, Optional
from datetime import datetime
import os
import sqlite3

from PySide6.QtCore import QObject, Property, Signal, Slot

from styles import TEAM_STATUS_COLORS
from utils import incident_context
from modules.operations.teams.data.team import Team
from modules.operations.teams.data import repository as team_repo


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

        # Display labels mapped to color/status keys used in palette
        self._status_options: list[dict[str, str]] = [
            {"label": "At Other Location", "key": "aol"},
            {"label": "Arrival", "key": "arrival"},
            {"label": "Assigned", "key": "assigned"},
            {"label": "Available", "key": "available"},
            {"label": "Break", "key": "break"},
            {"label": "Briefed", "key": "briefed"},
            {"label": "Rest", "key": "crew rest"},
            {"label": "Enroute", "key": "enroute"},
            {"label": "Out of Service", "key": "out of service"},
            {"label": "Report Writing", "key": "report writing"},
            {"label": "Returning to Base", "key": "returning"},
            {"label": "To Other Location", "key": "tol"},
            {"label": "Wheels Down", "key": "wheels down"},
            {"label": "Post Incident Management", "key": "post incident"},
            {"label": "Find", "key": "find"},
            {"label": "Complete", "key": "complete"},
        ]

    # ---- Properties exposed to QML ----
    @Property('QVariant', notify=teamChanged)
    def team(self) -> Dict[str, Any]:
        return self._team.to_qml()

    @Property('QVariant', constant=True)
    def statusList(self) -> list[dict]:
        return self._status_options

    @Property(bool, notify=teamChanged)
    def isAircraftTeam(self) -> bool:
        t = (self._team.team_type or "ground").lower()
        return t in {"air", "aircraft", "helo", "helicopter"}

    @Property('QVariant', notify=statusChanged)
    def teamStatusColor(self) -> Dict[str, str]:
        key = (self._team.status or "").strip().lower()
        st = TEAM_STATUS_COLORS.get(key)
        try:
            bg = st["bg"].color().name() if st else "#888888"
            fg = st["fg"].color().name() if st else "#000000"
        except Exception:
            bg, fg = "#888888", "#000000"
        return {"bg": bg, "fg": fg}

    # ---- Helpers -----------------------------------------------------
    def _get_person_role(self, person_id: int) -> Optional[str]:
        try:
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            db_path = os.path.join(base, "data", "master.db")
            with sqlite3.connect(db_path) as con:
                cur = con.execute("SELECT role FROM personnel WHERE id=?", (int(person_id),))
                row = cur.fetchone()
                if row and row[0]:
                    return str(row[0]).strip()
        except Exception:
            pass
        return None

    def _auto_set_pilot(self) -> None:
        if not self.isAircraftTeam:
            return
        roles = {int(m): (self._get_person_role(m) or "").strip().upper() for m in self._team.members}
        pic_members = [pid for pid, role in roles.items() if role == "PIC"]
        if pic_members:
            pilot_id = pic_members[-1]
            self._team.team_leader_id = pilot_id
            self._team.members = [m for m in self._team.members if roles[int(m)] != "PIC" or int(m) == pilot_id]

    # ---- Load/save ----
    @Slot(int)
    def loadTeam(self, team_id: int) -> None:
        try:
            if team_id:
                t = team_repo.get_team(int(team_id))
                self._team = t if t else Team(team_id=int(team_id))
            else:
                self._team = Team()
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

    # ---- Member/asset management ----
    @Slot(int)
    def addMember(self, person_id: int) -> None:
        if person_id not in self._team.members:
            self._team.members.append(int(person_id))
            self._auto_set_pilot()
            self.teamChanged.emit()

    @Slot(int)
    def removeMember(self, person_id: int) -> None:
        self._team.members = [p for p in self._team.members if int(p) != int(person_id)]
        if self._team.team_leader_id == int(person_id):
            self._team.team_leader_id = None
        self._auto_set_pilot()
        self.teamChanged.emit()

    @Slot(str)
    def addVehicle(self, vehicle_id: str) -> None:
        if vehicle_id and vehicle_id not in self._team.vehicles:
            self._team.vehicles.append(str(vehicle_id))
            self.teamChanged.emit()

    @Slot(str)
    def removeVehicle(self, vehicle_id: str) -> None:
        self._team.vehicles = [v for v in self._team.vehicles if str(v) != str(vehicle_id)]
        self.teamChanged.emit()

    @Slot(str)
    def addEquipment(self, eq_id: str) -> None:
        if eq_id and eq_id not in self._team.equipment:
            self._team.equipment.append(str(eq_id))
            self.teamChanged.emit()

    @Slot(str)
    def removeEquipment(self, eq_id: str) -> None:
        self._team.equipment = [e for e in self._team.equipment if str(e) != str(eq_id)]
        self.teamChanged.emit()

    @Slot(str)
    def addAircraft(self, ac_id: str) -> None:
        if ac_id and ac_id not in self._team.aircraft:
            self._team.aircraft.append(str(ac_id))
            self.teamChanged.emit()

    @Slot(str)
    def removeAircraft(self, ac_id: str) -> None:
        self._team.aircraft = [a for a in self._team.aircraft if str(a) != str(ac_id)]
        self.teamChanged.emit()

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

    @Slot(int)
    def setTeamLeader(self, person_id: int) -> None:
        try:
            if person_id is None:
                return
            if int(person_id) not in [int(p) for p in self._team.members]:
                # auto-add if not present
                self._team.members.append(int(person_id))
            self._team.team_leader_id = int(person_id)
            self.teamChanged.emit()
        except Exception as e:
            self.error.emit(f"Failed to set leader: {e}")

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
