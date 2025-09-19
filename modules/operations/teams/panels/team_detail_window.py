from __future__ import annotations

from typing import Any, Dict, Optional, List
from datetime import datetime

from PySide6.QtCore import QObject, Property, Signal, Slot, Qt, QTimer, QPoint
from PySide6.QtGui import QColor, QPalette, QTextOption
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

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
            self._emit_incident_refresh()
            self.saved.emit()
        except Exception as e:
            self.error.emit(f"Failed to save team: {e}")

    # ---- Needs Assistance ----
    @Slot()
    def raiseNeedsAssist(self) -> None:
        """Raise the team's needs-attention flag and persist to DB."""
        try:
            self._team.needs_attention = True
            self._persist_needs_attention(True)
            self.teamChanged.emit()
            self._emit_incident_refresh()
        except Exception as e:
            self.error.emit(f"Failed to flag needs assistance: {e}")

    @Slot()
    def clearNeedsAssist(self) -> None:
        """Clear the needs-attention flag and persist the change."""
        try:
            self._team.needs_attention = False
            self._persist_needs_attention(False)
            self.teamChanged.emit()
            self._emit_incident_refresh()
        except Exception as e:
            self.error.emit(f"Failed to clear needs assistance: {e}")

    # ---- Status ----
    def _default_status_key(self) -> str:
        for opt in self._status_options:
            key = str(opt.get("key", "")).strip().lower()
            if key == "available":
                return key
        if self._status_options:
            return str(self._status_options[0].get("key", "")).strip().lower()
        return ""

    @Slot(str)
    def setStatus(self, new_status: str) -> None:
        try:
            key = (new_status or "").strip()
            # Accept display labels or keys
            for opt in self._status_options:
                if key.lower() == opt["label"].lower():
                    key = opt["key"]
                    break
            normalized = str(key).strip().lower()
            if normalized == "wheels down" and not self.isAircraftTeam:
                fallback = self._default_status_key()
                normalized = fallback or "available"
            if not normalized:
                normalized = self._default_status_key()
            self._team.status = normalized
            if self._team.team_id:
                team_repo.set_team_status(int(self._team.team_id), self._team.status)
            self.statusChanged.emit(self._team.status)
            # Also request a board refresh
            self._emit_incident_refresh()
        except Exception as e:
            self.error.emit(f"Status change failed: {e}")

    @Slot(str)
    def setTeamType(self, code: str) -> None:
        self._team.team_type = str(code)
        if not self.isAircraftTeam and (self._team.status or "").strip().lower() == "wheels down":
            fallback = self._default_status_key() or "available"
            self._team.status = fallback
            if self._team.team_id:
                team_repo.set_team_status(int(self._team.team_id), self._team.status)
            self.statusChanged.emit(self._team.status)
            self._emit_incident_refresh()
        self.teamChanged.emit()

    # ---- Asset list providers (QML binds to these) ----
    @Slot(result='QVariant')
    def groundMembers(self) -> list[dict]:
        # Personnel for non-aircraft teams
        out: list[dict[str, Any]] = []
        lid = int(self._team.team_leader_id) if self._team.team_leader_id is not None else None
        for r in self._personnel:
            identifier = r.get("identifier") or r.get("callsign")
            out.append(
                {
                    "id": r.get("id"),
                    "identifier": identifier,
                    "callsign": r.get("callsign"),
                    "name": r.get("name"),
                    "rank": r.get("rank"),
                    "organization": r.get("organization"),
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
            identifier = r.get("identifier") or r.get("callsign")
            out.append(
                {
                    "id": r.get("id"),
                    "identifier": identifier,
                    "callsign": r.get("callsign"),
                    "name": r.get("name"),
                    "rank": r.get("rank"),
                    "organization": r.get("organization"),
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
                    "tail_number": r.get("tail_number"),
                    "callsign": r.get("callsign"),
                    "type": r.get("type"),
                    "status": r.get("status"),
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
                out.append({
                    "id": r.get("id"),
                    "callsign": r.get("callsign"),
                    "tail_number": r.get("tail_number"),
                    "status": r.get("status"),
                    "team_id": r.get("team_id"),
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
            members: list[int] = []
            for raw in getattr(self._team, "members", []) or []:
                try:
                    members.append(int(raw))
                except (TypeError, ValueError):
                    continue
            if not members:
                for rec in self._personnel or []:
                    pid = rec.get("id")
                    try:
                        if pid is not None:
                            members.append(int(pid))
                    except (TypeError, ValueError):
                        continue
                if members:
                    # Cache for future loads so we keep the derived order
                    self._team.members = members
            if not members:
                return
            try:
                current_leader = int(self._team.team_leader_id)
            except Exception:
                current_leader = None
            if current_leader is not None and current_leader in members:
                return
            self._team.team_leader_id = None
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

    def _persist_needs_attention(self, active: bool) -> None:
        if not self._team.team_id:
            return
        try:
            with team_repo._incident_connect() as con:  # type: ignore[attr-defined]
                try:
                    con.execute(
                        "UPDATE teams SET needs_attention=? WHERE id=?",
                        (1 if active else 0, int(self._team.team_id)),
                    )
                    con.commit()
                except Exception:
                    pass
        except Exception:
            pass

    def _emit_incident_refresh(self) -> None:
        try:
            inc = incident_context.get_active_incident_id()
            if inc:
                from utils.app_signals import app_signals as _sig

                _sig.incidentChanged.emit(str(inc))
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
        """Bulk-update primitive fields from form bindings without clearing unrelated values."""
        try:
            payload = data or {}
            if "name" in payload:
                self._team.name = str(payload.get("name") or "")
            if "callsign" in payload:
                value = payload.get("callsign")
                self._team.callsign = str(value) if value not in (None, "") else None
            if "role" in payload:
                value = payload.get("role")
                self._team.role = str(value) if value not in (None, "") else None
            if "priority" in payload:
                value = payload.get("priority")
                self._team.priority = int(value) if value not in (None, "") else None
            if "team_leader_id" in payload:
                value = payload.get("team_leader_id")
                self._team.team_leader_id = int(value) if value not in (None, "") else None
            if "team_type" in payload:
                value = payload.get("team_type")
                self._team.team_type = str(value) if value not in (None, "") else None
            if "primary_task" in payload:
                value = payload.get("primary_task")
                self._team.primary_task = str(value) if value not in (None, "") else None
            if "assignment" in payload:
                value = payload.get("assignment")
                self._team.assignment = str(value) if value not in (None, "") else None
            if "team_leader_phone" in payload:
                value = payload.get("team_leader_phone")
                self._team.team_leader_phone = str(value) if value not in (None, "") else None
            if "phone" in payload:
                value = payload.get("phone")
                self._team.phone = str(value) if value not in (None, "") else None
            if "notes" in payload:
                value = payload.get("notes")
                self._team.notes = str(value) if value not in (None, "") else None
            if "last_known_lat" in payload:
                lat = payload.get("last_known_lat")
                self._team.last_known_lat = float(lat) if lat not in (None, "") else None
            if "last_known_lon" in payload:
                lon = payload.get("last_known_lon")
                self._team.last_known_lon = float(lon) if lon not in (None, "") else None
            if "radio_ids" in payload:
                value = payload.get("radio_ids")
                self._team.radio_ids = str(value) if value not in (None, "") else None
            if "route" in payload:
                value = payload.get("route")
                self._team.route = str(value) if value not in (None, "") else None
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
            self._emit_incident_refresh()
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



class RefreshableComboBox(QComboBox):
    """Combo box that emits before showing the popup so options can refresh."""

    popupAboutToBeShown = Signal()

    def showPopup(self) -> None:  # type: ignore[override]
        self.popupAboutToBeShown.emit()
        super().showPopup()



class TeamDetailWindow(QMainWindow):
    """Widget-based implementation of the Team Detail window."""

    def __init__(
        self,
        team_id: Optional[int] = None,
        bridge: Optional[TeamDetailBridge] = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._bridge = bridge or TeamDetailBridge(self)
        self._team_id: Optional[int] = team_id
        self._is_air: bool = False
        self._updating: bool = False
        self._members_cache: List[Dict[str, Any]] = []
        self._asset_cache: List[Dict[str, Any]] = []
        self._equipment_cache: List[Dict[str, Any]] = []
        self._personnel_medic_column: Optional[int] = None
        self._assist_anim_state: bool = False
        self._status_options: List[Dict[str, Any]] = []
        self._filtered_status_options: List[Dict[str, str]] = []
        self._current_aircraft_id: Optional[int] = None
        self._refreshing_aircraft: bool = False

        self._notes_timer = QTimer(self)
        self._notes_timer.setSingleShot(True)
        self._notes_timer.setInterval(500)
        self._notes_timer.timeout.connect(self._commit_notes)

        self._assist_timer = QTimer(self)
        self._assist_timer.setInterval(700)
        self._assist_timer.timeout.connect(self._toggle_assist_strip)

        self.setWindowTitle("Team Detail")
        self.resize(980, 700)

        self._build_ui()
        self._populate_team_type_options()
        self._populate_status_options()

        self._bridge.teamChanged.connect(self._on_team_changed)
        self._bridge.statusChanged.connect(self._on_status_changed)
        self._bridge.error.connect(self._show_error)

        if self._team_id is not None:
            try:
                self._bridge.loadTeam(int(self._team_id))
            except Exception:
                self._on_team_changed()
        else:
            self._on_team_changed()

    # ---- UI construction ----
    def _build_ui(self) -> None:
        self._central = QWidget(self)
        self._central.setObjectName("teamDetailCentral")
        self._central.setAutoFillBackground(True)
        self.setCentralWidget(self._central)

        main_layout = QVBoxLayout(self._central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        self._title_label = QLabel("Team Detail")
        title_font = self._title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(20)
        self._title_label.setFont(title_font)
        main_layout.addWidget(self._title_label)

        self._assist_banner = QFrame()
        self._assist_banner.setObjectName("assistBanner")
        self._assist_banner.setVisible(False)
        self._assist_banner.setStyleSheet(
            "#assistBanner {"
            " background-color: #7a001a;"
            " border: 1px solid #ffb3c1;"
            " border-radius: 6px;"
            "}"
        )
        banner_layout = QVBoxLayout(self._assist_banner)
        banner_layout.setContentsMargins(0, 0, 0, 0)
        banner_layout.setSpacing(0)

        self._assist_strip = QFrame()
        self._assist_strip.setFixedHeight(3)
        self._assist_strip.setStyleSheet("background-color: #ff4d6d; border-radius: 2px;")
        banner_layout.addWidget(self._assist_strip)

        banner_row = QHBoxLayout()
        banner_row.setContentsMargins(10, 6, 10, 6)
        banner_row.setSpacing(8)
        banner_label = QLabel("⚠️  NEEDS ASSISTANCE")
        banner_label.setStyleSheet("color: white; font-weight: bold;")
        banner_row.addWidget(banner_label)
        banner_row.addStretch()
        banner_layout.addLayout(banner_row)
        main_layout.addWidget(self._assist_banner)

        overview_frame = QFrame()
        overview_frame.setObjectName("overviewFrame")
        overview_frame.setStyleSheet(
            "#overviewFrame {"
            " background-color: rgba(255, 255, 255, 0.92);"
            " border: 1px solid #d0d0d0;"
            " border-radius: 6px;"
            "}"
        )
        overview_layout = QVBoxLayout(overview_frame)
        overview_layout.setContentsMargins(10, 10, 10, 10)
        overview_layout.setSpacing(8)

        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(8)
        overview_layout.addLayout(grid)

        left_widget = QWidget()
        left_form = QFormLayout(left_widget)
        left_form.setContentsMargins(0, 0, 0, 0)
        left_form.setSpacing(8)
        left_form.setLabelAlignment(Qt.AlignRight)

        self._team_type_label = QLabel("Team Type")
        self._team_type_combo = QComboBox()
        left_form.addRow(self._team_type_label, self._team_type_combo)

        self._name_label = QLabel("Team Name")
        self._name_field = QLineEdit()
        left_form.addRow(self._name_label, self._name_field)

        self._aircraft_label = QLabel("Assigned Aircraft")
        self._aircraft_combo = RefreshableComboBox()
        self._aircraft_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self._aircraft_combo.setVisible(False)
        self._aircraft_label.setVisible(False)
        left_form.addRow(self._aircraft_label, self._aircraft_combo)

        self._leader_label = QLabel("Team Leader")
        self._leader_field = QLineEdit()
        self._leader_field.setReadOnly(True)
        left_form.addRow(self._leader_label, self._leader_field)

        self._phone_label = QLabel("Phone")
        self._phone_field = QLineEdit()
        self._phone_field.setReadOnly(True)
        left_form.addRow(self._phone_label, self._phone_field)

        self._status_label = QLabel("Status")
        self._status_combo = QComboBox()
        left_form.addRow(self._status_label, self._status_combo)

        grid.addWidget(left_widget, 0, 0)

        right_widget = QWidget()
        right_form = QFormLayout(right_widget)
        right_form.setContentsMargins(0, 0, 0, 0)
        right_form.setSpacing(8)
        right_form.setLabelAlignment(Qt.AlignRight)

        last_contact_label = QLabel("Last Contact")
        self._last_contact_value = QLabel("–")
        right_form.addRow(last_contact_label, self._last_contact_value)

        task_row_widget = QWidget()
        task_row_layout = QHBoxLayout(task_row_widget)
        task_row_layout.setContentsMargins(0, 0, 0, 0)
        task_row_layout.setSpacing(6)
        self._task_field = QLineEdit()
        self._task_field.setReadOnly(True)
        task_row_layout.addWidget(self._task_field)
        self._task_button = QPushButton("Link…")
        task_row_layout.addWidget(self._task_button)
        self._unlink_task_button = QPushButton("Unlink")
        self._unlink_task_button.setVisible(False)
        task_row_layout.addWidget(self._unlink_task_button)
        right_form.addRow(QLabel("Primary Task"), task_row_widget)

        self._assignment_field = QLineEdit()
        right_form.addRow(QLabel("Assignment"), self._assignment_field)

        grid.addWidget(right_widget, 0, 1)

        notes_label = QLabel("Notes")
        self._notes_edit = QTextEdit()
        self._notes_edit.setWordWrapMode(QTextOption.WordWrap)
        self._notes_edit.setFixedHeight(90)
        overview_layout.addWidget(notes_label)
        overview_layout.addWidget(self._notes_edit)

        main_layout.addWidget(overview_frame)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)
        self._edit_team_button = QPushButton("Edit Team")
        actions_layout.addWidget(self._edit_team_button)
        self._needs_assist_button = QPushButton("Flag Needs Assistance")
        actions_layout.addWidget(self._needs_assist_button)
        self._status_button = QPushButton("Update Status")
        actions_layout.addWidget(self._status_button)
        self._view_task_button = QPushButton("View Task")
        actions_layout.addWidget(self._view_task_button)
        actions_layout.addStretch()
        main_layout.addLayout(actions_layout)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setTabPosition(QTabWidget.North)
        main_layout.addWidget(self._tabs, 1)

        self._personnel_tab = QWidget()
        self._assets_tab = QWidget()
        self._equipment_tab = QWidget()
        self._logs_tab = QWidget()
        self._tabs.addTab(self._personnel_tab, "Personnel (Ground)")
        self._tabs.addTab(self._assets_tab, "Vehicles")
        self._tabs.addTab(self._equipment_tab, "Equipment")
        self._tabs.addTab(self._logs_tab, "Logs")

        personnel_layout = QVBoxLayout(self._personnel_tab)
        personnel_layout.setContentsMargins(0, 0, 0, 0)
        personnel_layout.setSpacing(8)
        member_buttons = QHBoxLayout()
        member_buttons.setSpacing(6)
        self._add_member_button = QPushButton("Add Personnel")
        member_buttons.addWidget(self._add_member_button)
        member_buttons.addStretch()
        self._member_detail_button = QPushButton("Detail")
        self._member_detail_button.setEnabled(False)
        member_buttons.addWidget(self._member_detail_button)
        personnel_layout.addLayout(member_buttons)

        self._personnel_table = QTableWidget()
        self._personnel_table.setAlternatingRowColors(True)
        self._personnel_table.verticalHeader().setVisible(False)
        self._personnel_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._personnel_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._personnel_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._personnel_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._personnel_table.customContextMenuRequested.connect(self._show_personnel_menu)
        self._personnel_table.itemSelectionChanged.connect(self._on_member_selection_changed)
        self._configure_personnel_header()
        personnel_layout.addWidget(self._personnel_table)

        assets_layout = QVBoxLayout(self._assets_tab)
        assets_layout.setContentsMargins(0, 0, 0, 0)
        assets_layout.setSpacing(8)
        asset_buttons = QHBoxLayout()
        asset_buttons.setSpacing(6)
        self._asset_add_button = QPushButton("Add Vehicle")
        asset_buttons.addWidget(self._asset_add_button)
        asset_buttons.addStretch()
        assets_layout.addLayout(asset_buttons)

        self._asset_table = QTableWidget()
        self._asset_table.setAlternatingRowColors(True)
        self._asset_table.verticalHeader().setVisible(False)
        self._asset_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._asset_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._asset_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        assets_layout.addWidget(self._asset_table)

        equipment_layout = QVBoxLayout(self._equipment_tab)
        equipment_layout.setContentsMargins(0, 0, 0, 0)
        equipment_layout.setSpacing(8)
        equipment_buttons = QHBoxLayout()
        equipment_buttons.setSpacing(6)
        self._equipment_add_button = QPushButton("Add Equipment")
        equipment_buttons.addWidget(self._equipment_add_button)
        equipment_buttons.addStretch()
        equipment_layout.addLayout(equipment_buttons)

        self._equipment_table = QTableWidget()
        self._equipment_table.setAlternatingRowColors(True)
        self._equipment_table.verticalHeader().setVisible(False)
        self._equipment_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._equipment_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._equipment_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        equipment_layout.addWidget(self._equipment_table)

        logs_layout = QVBoxLayout(self._logs_tab)
        logs_layout.setContentsMargins(0, 0, 0, 0)
        logs_layout.setSpacing(8)
        placeholder = QLabel("Logs will appear here when implemented.")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("color: #555555;")
        logs_layout.addWidget(placeholder)
        self._tabs.setTabEnabled(3, False)

        # Connections for form controls
        self._team_type_combo.currentIndexChanged.connect(self._handle_team_type_changed)
        self._status_combo.currentIndexChanged.connect(self._handle_status_changed)
        self._name_field.editingFinished.connect(self._handle_name_edited)
        self._assignment_field.editingFinished.connect(self._handle_assignment_edited)
        self._notes_edit.textChanged.connect(self._on_notes_changed)
        self._task_button.clicked.connect(self._handle_task_button)
        self._unlink_task_button.clicked.connect(self._handle_unlink_task)
        self._edit_team_button.clicked.connect(self._handle_edit_team)
        self._needs_assist_button.clicked.connect(self._handle_needs_assist)
        self._status_button.clicked.connect(self._status_combo.showPopup)
        self._view_task_button.clicked.connect(self._handle_view_task)
        self._add_member_button.clicked.connect(self._handle_add_member)
        self._member_detail_button.clicked.connect(self._handle_member_detail)
        self._asset_add_button.clicked.connect(self._handle_add_asset)
        self._equipment_add_button.clicked.connect(self._handle_add_equipment)
        self._aircraft_combo.popupAboutToBeShown.connect(self._refresh_aircraft_options)
        self._aircraft_combo.currentIndexChanged.connect(self._handle_aircraft_selected)

    # ---- Data refresh helpers ----
    def _configure_personnel_header(self) -> None:
        header = self._personnel_table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setHighlightSections(False)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(23)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setStyleSheet(
            "QHeaderView::section {"
            " background-color: #f5f5f5;"
            " border-right: 1px solid #c5c5c5;"
            " border-bottom: 1px solid #c5c5c5;"
            " padding: 6px 8px;"
            "}"
            "QHeaderView::section:last { border-right: 0; }"
        )

    def _make_checkbox_cell(self, checked: bool) -> tuple[QWidget, QCheckBox]:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)
        box = QCheckBox(container)
        box.setChecked(checked)
        layout.addWidget(box)
        return container, box

    def _populate_team_type_options(self) -> None:
        options = getattr(self._bridge, "teamTypeList", []) or []
        self._team_type_combo.blockSignals(True)
        self._team_type_combo.clear()
        for opt in options:
            label = str(opt.get("label", ""))
            code = str(opt.get("code", ""))
            self._team_type_combo.addItem(label, code)
        self._team_type_combo.blockSignals(False)

    def _populate_status_options(self) -> None:
        options = getattr(self._bridge, "statusList", []) or []
        normalized: List[Dict[str, str]] = []
        for opt in options:
            label = str(opt.get("label", ""))
            key = str(opt.get("key", label)).strip().lower()
            normalized.append({"label": label, "key": key})
        self._status_options = normalized
        self._reload_status_options()

    def _reload_status_options(self) -> None:
        filtered: List[Dict[str, str]] = []
        for opt in self._status_options:
            key = str(opt.get("key", "")).strip().lower()
            if not self._is_air and key == "wheels down":
                continue
            filtered.append({"label": opt.get("label", ""), "key": key})
        self._filtered_status_options = filtered
        self._status_combo.blockSignals(True)
        self._status_combo.clear()
        for opt in filtered:
            self._status_combo.addItem(opt["label"], opt["key"])
        self._status_combo.blockSignals(False)

    def _status_fallback_key(self) -> Optional[str]:
        for opt in self._filtered_status_options:
            key = opt.get("key")
            if key == "available":
                return key
        if self._filtered_status_options:
            return self._filtered_status_options[0].get("key")
        return None

    def _on_team_changed(self) -> None:
        self._updating = True
        team = self._bridge.team if hasattr(self._bridge, "team") else {}
        team = team or {}
        self._is_air = bool(getattr(self._bridge, "isAircraftTeam", False))
        try:
            self._members_cache = (
                self._bridge.aircrewMembers() if self._is_air else self._bridge.groundMembers()
            )
        except Exception:
            self._members_cache = []
        try:
            self._asset_cache = (
                self._bridge.aircraft() if self._is_air else self._bridge.vehicles()
            )
        except Exception:
            self._asset_cache = []
        try:
            self._equipment_cache = self._bridge.equipment()
        except Exception:
            self._equipment_cache = []

        self._apply_team_type_ui()
        self._update_background()
        self._update_title(team)
        self._populate_team_type_selection(team)
        self._populate_status_selection(team)
        self._update_leader_fields(team)
        self._update_name_assignment_fields(team)
        self._update_last_contact(team)
        self._update_task_widgets(team)
        self._update_notes_field(team)
        self._populate_personnel_table(self._members_cache)
        self._populate_assets_table(self._asset_cache)
        self._update_aircraft_assignment_display()
        self._populate_equipment_table(self._equipment_cache)
        self._update_assistance_ui()
        self._update_member_detail_button()
        self._apply_status_palette()

        self._updating = False

    def _on_status_changed(self, status_key: str) -> None:
        if self._updating:
            return
        self._populate_status_selection({"status": status_key})
        self._apply_status_palette()

    def _apply_team_type_ui(self) -> None:
        if self._is_air:
            self._name_label.setText("Callsign")
            self._leader_label.setText("Pilot")
            self._tabs.setTabText(0, "Aircrew")
            self._tabs.setTabText(1, "Aircraft")
            self._add_member_button.setText("Add Aircrew")
            self._asset_add_button.setText("Add Aircraft")
            self._asset_add_button.setVisible(False)
            self._aircraft_label.setVisible(True)
            self._aircraft_combo.setVisible(True)
        else:
            self._name_label.setText("Team Name")
            self._leader_label.setText("Team Leader")
            self._tabs.setTabText(0, "Personnel (Ground)")
            self._tabs.setTabText(1, "Vehicles")
            self._add_member_button.setText("Add Personnel")
            self._asset_add_button.setText("Add Vehicle")
            self._asset_add_button.setVisible(True)
            self._aircraft_label.setVisible(False)
            self._aircraft_combo.setVisible(False)
        self._reload_status_options()

    def _update_title(self, team: Dict[str, Any]) -> None:
        parts: List[str] = []
        team_type = str(team.get("team_type", "")).upper()
        if team_type:
            parts.append(team_type)
        name = ""
        if self._is_air:
            name = team.get("callsign") or team.get("name") or ""
        else:
            name = team.get("name") or ""
        if name:
            parts.append(str(name))
        leader_id = team.get("team_leader_id")
        leader_last = ""
        if leader_id is not None:
            try:
                leader_name = self._bridge.leaderName(int(leader_id))  # type: ignore[arg-type]
            except Exception:
                leader_name = ""
            if leader_name:
                bits = str(leader_name).strip().split()
                if bits:
                    leader_last = bits[-1]
        if leader_last:
            parts.append(leader_last)
        title = " - ".join(p for p in parts if p)
        self._title_label.setText(title or "Team Detail")
        if name:
            self.setWindowTitle(f"Team Detail - {name}")
        else:
            self.setWindowTitle("Team Detail")

    def _populate_team_type_selection(self, team: Dict[str, Any]) -> None:
        current = str(team.get("team_type", ""))
        self._team_type_combo.blockSignals(True)
        index = self._team_type_combo.findData(current)
        if index == -1:
            index = self._team_type_combo.findData(current.upper())
        if index >= 0:
            self._team_type_combo.setCurrentIndex(index)
        self._team_type_combo.blockSignals(False)

    def _populate_status_selection(self, team: Dict[str, Any]) -> None:
        status = str(team.get("status", "")).strip().lower()
        if not self._is_air and status == "wheels down":
            fallback = self._status_fallback_key()
            if fallback and fallback != status:
                try:
                    self._bridge.setStatus(str(fallback))
                    status = str(fallback)
                except Exception:
                    status = str(fallback)
        self._status_combo.blockSignals(True)
        index = self._status_combo.findData(status)
        if index < 0 and status:
            index = self._status_combo.findData(str(status).lower())
        if index >= 0:
            self._status_combo.setCurrentIndex(index)
        else:
            fallback = self._status_fallback_key()
            if fallback is not None:
                idx = self._status_combo.findData(fallback)
                if idx >= 0:
                    self._status_combo.setCurrentIndex(idx)
        self._status_combo.blockSignals(False)

    def _format_aircraft_label(self, record: Dict[str, Any]) -> str:
        callsign = str(record.get("callsign") or "").strip()
        tail = str(
            record.get("tail_number")
            or record.get("tail")
            or record.get("tailNumber")
            or ""
        ).strip()
        status = str(record.get("status") or "").strip()
        if not callsign:
            fallback = tail or record.get("identifier") or record.get("id")
            callsign = str(fallback or "—").strip()
        if not tail:
            tail = "—"
        if not status:
            status = "—"
        return f"{callsign or '—'} - {tail} - {status}"

    def _update_aircraft_assignment_display(self) -> None:
        if not hasattr(self, "_aircraft_combo"):
            return
        self._refreshing_aircraft = True
        try:
            self._aircraft_combo.blockSignals(True)
            self._aircraft_combo.clear()
            self._aircraft_combo.addItem("No Aircraft Assigned", None)
            current_id: Optional[int] = None
            if self._is_air:
                self._aircraft_combo.setEnabled(True)
                current_record = None
                for rec in self._asset_cache:
                    if rec.get("id") is not None:
                        current_record = rec
                        break
                if current_record:
                    current_id = current_record.get("id")
                    label = self._format_aircraft_label(current_record)
                    self._aircraft_combo.addItem(label, current_id)
                    self._aircraft_combo.setCurrentIndex(1)
                else:
                    self._aircraft_combo.setCurrentIndex(0)
            else:
                self._aircraft_combo.setEnabled(False)
                self._aircraft_combo.setCurrentIndex(0)
            self._current_aircraft_id = (
                int(current_id) if current_id is not None and str(current_id) != "" else None
            )
        finally:
            self._aircraft_combo.blockSignals(False)
            self._refreshing_aircraft = False

    def _refresh_aircraft_options(self) -> None:
        if not self._is_air or not hasattr(self, "_aircraft_combo"):
            return
        try:
            options = self._bridge.availableAircraft() if hasattr(self._bridge, "availableAircraft") else []
        except Exception:
            options = []
        current_id = self._current_aircraft_id
        self._refreshing_aircraft = True
        try:
            self._aircraft_combo.blockSignals(True)
            self._aircraft_combo.clear()
            self._aircraft_combo.addItem("No Aircraft Assigned", None)
            seen: set[str] = set()
            for opt in options or []:
                opt_id = opt.get("id")
                label = self._format_aircraft_label(opt)
                self._aircraft_combo.addItem(label, opt_id)
                if opt_id is not None and str(opt_id) != "":
                    seen.add(str(opt_id))
            if current_id is not None and str(current_id) not in seen:
                for rec in self._asset_cache:
                    if str(rec.get("id")) == str(current_id):
                        label = self._format_aircraft_label(rec)
                        self._aircraft_combo.addItem(label, current_id)
                        break
            target = current_id if current_id is not None else None
            idx = self._aircraft_combo.findData(target)
            if idx >= 0:
                self._aircraft_combo.setCurrentIndex(idx)
            else:
                self._aircraft_combo.setCurrentIndex(0)
        finally:
            self._aircraft_combo.blockSignals(False)
            self._refreshing_aircraft = False

    def _handle_aircraft_selected(self, index: int) -> None:
        if self._updating or self._refreshing_aircraft or not hasattr(self, "_aircraft_combo"):
            return
        data = self._aircraft_combo.itemData(index)
        target = data if data not in ("", None) else None
        if self._current_aircraft_id is None and target is None:
            return
        if target is not None and self._current_aircraft_id is not None:
            try:
                if int(target) == int(self._current_aircraft_id):
                    return
            except Exception:
                pass
        try:
            self._bridge.setSingleAircraft(target)
            self._current_aircraft_id = (
                int(target) if target is not None and str(target) != "" else None
            )
        except Exception:
            pass

    def _update_leader_fields(self, team: Dict[str, Any]) -> None:
        leader_id = team.get("team_leader_id")
        leader_name = ""
        leader_phone = team.get("team_leader_phone") or team.get("phone") or ""
        if leader_id is not None:
            try:
                leader_name = self._bridge.leaderName(int(leader_id))
            except Exception:
                leader_name = ""
            for member in self._members_cache:
                if str(member.get("id")) == str(leader_id):
                    leader_phone = member.get("phone") or leader_phone or ""
                    break
        self._leader_field.setText(leader_name or "")
        self._phone_field.setText(str(leader_phone or ""))

    def _update_name_assignment_fields(self, team: Dict[str, Any]) -> None:
        name_value = team.get("name") or ""
        callsign_value = team.get("callsign") or ""
        display_name = callsign_value if self._is_air else name_value
        if self._is_air and not display_name:
            display_name = name_value
        self._name_field.blockSignals(True)
        self._name_field.setText(str(display_name or ""))
        self._name_field.blockSignals(False)

        assignment = team.get("assignment") or ""
        self._assignment_field.blockSignals(True)
        self._assignment_field.setText(str(assignment or ""))
        self._assignment_field.blockSignals(False)

    def _update_last_contact(self, team: Dict[str, Any]) -> None:
        ts = team.get("last_comm_ts") or team.get("last_contact_ts") or team.get("last_update_ts")
        label = "–"
        if ts:
            try:
                dt = datetime.fromisoformat(str(ts))
                label = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                label = str(ts)
        self._last_contact_value.setText(label)

    def _update_task_widgets(self, team: Dict[str, Any]) -> None:
        task_id = team.get("current_task_id") or team.get("primary_task_id")
        task_display = str(task_id) if task_id else ""
        self._task_field.setText(task_display)
        if task_id:
            self._task_button.setText("Open")
            self._unlink_task_button.setVisible(True)
        else:
            self._task_button.setText("Link…")
            self._unlink_task_button.setVisible(False)
        self._view_task_button.setEnabled(bool(task_id))

    def _update_notes_field(self, team: Dict[str, Any]) -> None:
        notes = team.get("notes") or ""
        self._notes_timer.stop()
        self._notes_edit.blockSignals(True)
        self._notes_edit.setPlainText(str(notes))
        self._notes_edit.blockSignals(False)

    def _populate_personnel_table(self, members: List[Dict[str, Any]]) -> None:
        if self._is_air:
            headers = [
                "ID",
                "Name",
                "Rank",
                "Organization",
                "Role",
                "Phone",
                "Certifications",
                "PIC",
                "Actions",
            ]
            default_widths = [110, 220, 90, 160, 150, 150, 150, 80, 110]
        else:
            headers = [
                "ID",
                "Name",
                "Rank",
                "Organization",
                "Role",
                "Phone",
                "Leader",
                "Medic",
                "Actions",
            ]
            default_widths = [110, 220, 90, 160, 150, 150, 80, 80, 110]

        self._personnel_table.clear()
        self._personnel_table.setRowCount(len(members))
        self._personnel_table.setColumnCount(len(headers))
        self._personnel_table.setHorizontalHeaderLabels(headers)
        self._configure_personnel_header()

        try:
            roles = self._bridge.teamRoleOptions() or []
        except Exception:
            roles = []

        identifier_col = 0
        name_col = 1
        rank_col = 2
        org_col = 3
        role_col = 4
        phone_col = 5
        actions_col = len(headers) - 1

        self._personnel_medic_column = None
        if self._is_air:
            cert_col = 6
            leader_col = 7
        else:
            leader_col = 6
            self._personnel_medic_column = 7

        header = self._personnel_table.horizontalHeader()
        for col in range(len(headers)):
            header.setSectionResizeMode(col, QHeaderView.Interactive)
        for col, width in enumerate(default_widths):
            if col < len(headers):
                header.resizeSection(col, width)

        for row, member in enumerate(members):
            member_id = member.get("id")
            identifier_value = member.get("identifier") or member.get("callsign")
            if not identifier_value and member_id is not None:
                identifier_value = member_id
            id_item = QTableWidgetItem(str(identifier_value or ""))
            id_item.setData(Qt.UserRole, member_id)
            id_item.setTextAlignment(Qt.AlignCenter)
            if member_id is not None:
                id_item.setToolTip(f"Record #{member_id}")
            self._personnel_table.setItem(row, identifier_col, id_item)

            name_item = QTableWidgetItem(str(member.get("name") or ""))
            self._personnel_table.setItem(row, name_col, name_item)

            rank_item = QTableWidgetItem(str(member.get("rank") or ""))
            rank_item.setTextAlignment(Qt.AlignCenter)
            self._personnel_table.setItem(row, rank_col, rank_item)

            org_item = QTableWidgetItem(str(member.get("organization") or ""))
            org_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self._personnel_table.setItem(row, org_col, org_item)

            role_combo = QComboBox()
            role_combo.addItem("", "")
            for role in roles:
                role_combo.addItem(str(role), role)
            current_role = member.get("role") or ""
            role_combo.blockSignals(True)
            if current_role:
                idx = role_combo.findData(current_role)
                if idx == -1:
                    idx = role_combo.findText(str(current_role))
                if idx >= 0:
                    role_combo.setCurrentIndex(idx)
            role_combo.blockSignals(False)
            role_combo.currentIndexChanged.connect(
                lambda idx, pid=member_id, combo=role_combo: self._on_role_changed(pid, combo.itemData(idx))
            )
            self._personnel_table.setCellWidget(row, role_col, role_combo)

            phone_item = QTableWidgetItem(str(member.get("phone") or ""))
            phone_item.setTextAlignment(Qt.AlignCenter)
            self._personnel_table.setItem(row, phone_col, phone_item)

            if self._is_air:
                certs_item = QTableWidgetItem(str(member.get("certs") or ""))
                self._personnel_table.setItem(row, cert_col, certs_item)
                leader_container, leader_box = self._make_checkbox_cell(bool(member.get("isPIC")))
                leader_box.setToolTip("Mark this member as PIC")
                leader_box.setEnabled(member_id is not None)
                leader_box.clicked.connect(
                    lambda checked, pid=member_id, box=leader_box: self._on_leader_clicked(pid, checked, box)
                )
                self._personnel_table.setCellWidget(row, leader_col, leader_container)
            else:
                leader_container, leader_box = self._make_checkbox_cell(bool(member.get("isLeader")))
                leader_box.setToolTip("Set this member as the team leader")
                leader_box.setEnabled(member_id is not None)
                leader_box.clicked.connect(
                    lambda checked, pid=member_id, box=leader_box: self._on_leader_clicked(pid, checked, box)
                )
                self._personnel_table.setCellWidget(row, leader_col, leader_container)
                medic_col = self._personnel_medic_column
                if medic_col is not None:
                    medic_container, medic_box = self._make_checkbox_cell(bool(member.get("isMedic")))
                    medic_box.setToolTip("Toggle medic status")
                    medic_box.setEnabled(member_id is not None)
                    medic_box.stateChanged.connect(
                        lambda state, pid=member_id: self._on_medic_toggled(pid, state)
                    )
                    self._personnel_table.setCellWidget(row, medic_col, medic_container)

            remove_btn = QPushButton("Remove")
            remove_btn.setEnabled(member_id is not None)
            remove_btn.clicked.connect(
                lambda _=False, pid=member_id: self._bridge.removeMember(pid) if pid is not None else None
            )
            self._personnel_table.setCellWidget(row, actions_col, remove_btn)

    def _populate_assets_table(self, assets: List[Dict[str, Any]]) -> None:
        if self._is_air:
            headers = ["ID", "Callsign", "Tail Number", "Type", "Status"]
        else:
            headers = ["ID", "Callsign/Name", "Type", "Driver", "Phone", "Actions"]
        self._asset_table.clear()
        self._asset_table.setRowCount(len(assets))
        self._asset_table.setColumnCount(len(headers))
        self._asset_table.setHorizontalHeaderLabels(headers)

        for row, asset in enumerate(assets):
            asset_id = asset.get("id")
            id_item = QTableWidgetItem(str(asset_id) if asset_id is not None else "")
            id_item.setData(Qt.UserRole, asset_id)
            id_item.setTextAlignment(Qt.AlignCenter)
            self._asset_table.setItem(row, 0, id_item)

            if self._is_air:
                callsign_item = QTableWidgetItem(str(asset.get("callsign") or ""))
                self._asset_table.setItem(row, 1, callsign_item)

                tail_value = asset.get("tail") or asset.get("tail_number")
                tail_item = QTableWidgetItem(str(tail_value or ""))
                self._asset_table.setItem(row, 2, tail_item)

                type_item = QTableWidgetItem(str(asset.get("type") or ""))
                self._asset_table.setItem(row, 3, type_item)

                status_item = QTableWidgetItem(str(asset.get("status") or ""))
                self._asset_table.setItem(row, 4, status_item)
            else:
                label_value = asset.get("callsign") or asset.get("name") or ""
                label_item = QTableWidgetItem(str(label_value))
                self._asset_table.setItem(row, 1, label_item)

                type_item = QTableWidgetItem(str(asset.get("type") or ""))
                self._asset_table.setItem(row, 2, type_item)

                driver_value = asset.get("driver")
                driver_item = QTableWidgetItem(str(driver_value or ""))
                self._asset_table.setItem(row, 3, driver_item)

                comm_value = asset.get("comms") or asset.get("phone") or ""
                comm_item = QTableWidgetItem(str(comm_value))
                self._asset_table.setItem(row, 4, comm_item)

                remove_btn = QPushButton("Remove")
                remove_btn.clicked.connect(
                    lambda _=False, aid=asset_id: self._bridge.removeAsset(aid) if aid is not None else None
                )
                self._asset_table.setCellWidget(row, len(headers) - 1, remove_btn)

        header = self._asset_table.horizontalHeader()
        for col in range(len(headers)):
            if self._is_air:
                mode = QHeaderView.ResizeToContents
                if col == 2:
                    mode = QHeaderView.Stretch
            else:
                mode = QHeaderView.ResizeToContents
                if col == 1:
                    mode = QHeaderView.Stretch
            header.setSectionResizeMode(col, mode)

    def _populate_equipment_table(self, equipment: List[Dict[str, Any]]) -> None:
        headers = ["ID", "Name", "Qty", "Notes", "Actions"]
        self._equipment_table.clear()
        self._equipment_table.setRowCount(len(equipment))
        self._equipment_table.setColumnCount(len(headers))
        self._equipment_table.setHorizontalHeaderLabels(headers)

        for row, item in enumerate(equipment):
            eq_id = item.get("id")
            id_item = QTableWidgetItem(str(eq_id) if eq_id is not None else "")
            id_item.setData(Qt.UserRole, eq_id)
            id_item.setTextAlignment(Qt.AlignCenter)
            self._equipment_table.setItem(row, 0, id_item)

            name_item = QTableWidgetItem(str(item.get("name") or ""))
            self._equipment_table.setItem(row, 1, name_item)

            qty_item = QTableWidgetItem(str(item.get("qty") or ""))
            qty_item.setTextAlignment(Qt.AlignCenter)
            self._equipment_table.setItem(row, 2, qty_item)

            notes_item = QTableWidgetItem(str(item.get("notes") or ""))
            self._equipment_table.setItem(row, 3, notes_item)

            remove_btn = QPushButton("Remove")
            remove_btn.clicked.connect(
                lambda _=False, eid=eq_id: self._bridge.removeEquipment(eid) if eid is not None else None
            )
            self._equipment_table.setCellWidget(row, len(headers) - 1, remove_btn)

        header = self._equipment_table.horizontalHeader()
        for col in range(len(headers)):
            mode = QHeaderView.ResizeToContents
            if col == 3:
                mode = QHeaderView.Stretch
            header.setSectionResizeMode(col, mode)

    def _update_assistance_ui(self) -> None:
        needs_assist = bool(getattr(self._bridge, "needsAssistActive", False))
        self._assist_banner.setVisible(needs_assist)
        if needs_assist:
            if not self._assist_timer.isActive():
                self._assist_anim_state = False
                self._assist_timer.start()
            self._needs_assist_button.setText("NEEDS ASSISTANCE")
            self._needs_assist_button.setStyleSheet(
                "QPushButton { background-color: #c1121f; color: white; font-weight: bold; }"
            )
            self._needs_assist_button.setToolTip("Clear the needs-assistance flag")
        else:
            self._assist_timer.stop()
            self._assist_strip.setStyleSheet("background-color: #ff4d6d; border-radius: 2px;")
            self._needs_assist_button.setText("Flag Needs Assistance")
            self._needs_assist_button.setStyleSheet("")
            self._needs_assist_button.setToolTip("Mark this team as needing assistance")

    def _apply_status_palette(self) -> None:
        try:
            colors = self._bridge.teamStatusColor
        except Exception:
            colors = {"bg": "#888888", "fg": "#000000"}
        bg = colors.get("bg", "#888888")
        fg = colors.get("fg", "#000000")
        self._status_combo.setStyleSheet(
            f"QComboBox {{ background-color: {bg}; color: {fg}; font-weight: bold; }}"
        )

    def _update_background(self) -> None:
        try:
            color_str = getattr(self._bridge, "teamTypeColor", "#f0f0f0")
        except Exception:
            color_str = "#f0f0f0"
        color = QColor(str(color_str))
        if not color.isValid():
            color = QColor("#f0f0f0")
        base = color.lighter(130)
        palette = self._central.palette()
        palette.setColor(QPalette.Window, base)
        self._central.setPalette(palette)

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Team Detail", message)

    def _handle_team_type_changed(self, index: int) -> None:
        if self._updating:
            return
        code = self._team_type_combo.itemData(index)
        if code is None:
            return
        try:
            self._bridge.setTeamType(code)
        except Exception:
            pass

    def _handle_status_changed(self, index: int) -> None:
        if self._updating:
            return
        key = self._status_combo.itemData(index)
        if key is None:
            return
        try:
            self._bridge.setStatus(str(key))
        except Exception:
            pass

    def _handle_name_edited(self) -> None:
        if self._updating:
            return
        value = self._name_field.text().strip()
        payload = {"callsign": value} if self._is_air else {"name": value}
        try:
            self._bridge.updateFromQml(payload)
        except Exception:
            pass

    def _handle_assignment_edited(self) -> None:
        if self._updating:
            return
        value = self._assignment_field.text().strip()
        try:
            self._bridge.updateFromQml({"assignment": value})
        except Exception:
            pass

    def _on_notes_changed(self) -> None:
        if self._updating:
            return
        self._notes_timer.start()

    def _commit_notes(self) -> None:
        if self._updating:
            return
        text = self._notes_edit.toPlainText()
        try:
            self._bridge.updateFromQml({"notes": text})
        except Exception:
            pass

    def _handle_task_button(self) -> None:
        team = self._bridge.team if hasattr(self._bridge, "team") else {}
        task_id = team.get("current_task_id") or team.get("primary_task_id")
        if task_id:
            self._handle_view_task()
            return
        dialog = getattr(self._bridge, "linkTaskDialog", None)
        if dialog and hasattr(dialog, "open"):
            dialog.open()
            return
        QMessageBox.information(
            self,
            "Link Task",
            "Linking a task requires the task linking dialog, which is not available.",
        )

    def _handle_unlink_task(self) -> None:
        team = self._bridge.team if hasattr(self._bridge, "team") else {}
        task_id = team.get("current_task_id") or team.get("primary_task_id")
        if task_id and hasattr(self._bridge, "unlinkTask"):
            try:
                self._bridge.unlinkTask(int(task_id))
            except Exception:
                pass

    def _handle_view_task(self) -> None:
        handler = getattr(self._bridge, "openTaskDetail", None)
        if callable(handler):
            handler()

    def _handle_needs_assist(self) -> None:
        active = bool(getattr(self._bridge, "needsAssistActive", False))
        if active:
            response = QMessageBox.question(
                self,
                "Clear Needs Assistance",
                "Mark this team as no longer needing assistance?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if response != QMessageBox.Yes:
                return
            handler = getattr(self._bridge, "clearNeedsAssist", None)
        else:
            handler = getattr(self._bridge, "raiseNeedsAssist", None)
        if callable(handler):
            handler()

    def _handle_edit_team(self) -> None:
        handler = getattr(self._bridge, "openEditTeam", None)
        if callable(handler):
            handler()

    def _handle_add_member(self) -> None:
        handler = getattr(self._bridge, "addMember", None)
        if callable(handler):
            handler()

    def _handle_member_detail(self) -> None:
        handler = getattr(self._bridge, "openSelectedMember", None)
        if callable(handler):
            handler()

    def _handle_add_asset(self) -> None:
        handler = getattr(self._bridge, "addAsset", None)
        if callable(handler):
            handler()

    def _handle_add_equipment(self) -> None:
        handler = getattr(self._bridge, "addEquipment", None)
        if callable(handler):
            handler()

    def _on_member_selection_changed(self) -> None:
        has_selection = bool(self._personnel_table.selectionModel().selectedRows())
        handler = getattr(self._bridge, "openSelectedMember", None)
        self._member_detail_button.setEnabled(bool(has_selection and callable(handler)))

    def _show_personnel_menu(self, pos: QPoint) -> None:
        row = self._personnel_table.rowAt(pos.y())
        if row < 0:
            return
        item = self._personnel_table.item(row, 0)
        if item is None:
            return
        person_id = item.data(Qt.UserRole)
        if person_id is None:
            return
        menu = QMenu(self)
        label = "Set as PIC" if self._is_air else "Set as Leader"
        menu.addAction(label, lambda: self._bridge.setLeader(person_id))
        if not self._is_air and self._personnel_medic_column is not None:
            widget = self._personnel_table.cellWidget(row, self._personnel_medic_column)
            is_medic = bool(widget.isChecked()) if isinstance(widget, QCheckBox) else False
            toggle_text = "Unset Medic" if is_medic else "Mark as Medic"
            menu.addAction(
                toggle_text,
                lambda: self._bridge.setMedic(person_id, not is_medic),
            )
        menu.addAction("Remove", lambda: self._bridge.removeMember(person_id))
        menu.exec(self._personnel_table.viewport().mapToGlobal(pos))

    def _on_role_changed(self, person_id: Any, value: Any) -> None:
        if self._updating or person_id is None:
            return
        role_value = value if value not in (None, "") else None
        try:
            self._bridge.setPersonRole(int(person_id), role_value)
        except Exception:
            pass

    def _on_leader_clicked(self, person_id: Any, checked: bool, checkbox: QCheckBox) -> None:
        if self._updating or person_id is None:
            return
        if not checked:
            checkbox.blockSignals(True)
            checkbox.setChecked(True)
            checkbox.blockSignals(False)
            return
        try:
            self._bridge.setLeader(int(person_id))
        except Exception:
            pass

    def _on_medic_toggled(self, person_id: Any, state: int) -> None:
        if self._updating or person_id is None:
            return
        handler = getattr(self._bridge, "setMedic", None)
        if callable(handler):
            try:
                handler(int(person_id), state == Qt.Checked)
            except Exception:
                pass

    def _toggle_assist_strip(self) -> None:
        self._assist_anim_state = not self._assist_anim_state
        color = "#ff4d6d" if self._assist_anim_state else "#ffb3c1"
        self._assist_strip.setStyleSheet(f"background-color: {color}; border-radius: 2px;")

    def _update_member_detail_button(self) -> None:
        handler = getattr(self._bridge, "openSelectedMember", None)
        enabled = bool(callable(handler) and self._personnel_table.selectionModel().hasSelection())
        self._member_detail_button.setEnabled(enabled)




