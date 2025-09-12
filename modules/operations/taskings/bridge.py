from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from PySide6.QtCore import QObject, Slot


def _to_variant(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, (list, tuple)):
        return [_to_variant(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_variant(v) for k, v in obj.items()}
    return obj


class TaskingsBridge(QObject):
    """Lightweight in-process bridge for QML to access taskings API functions.

    Calls the FastAPI router functions directly (no HTTP), converting dataclasses
    to QVariant-compatible dicts/lists for QML.
    """

    @Slot(result="QVariant")
    def getLookups(self) -> Any:  # noqa: N802 (Qt slot naming)
        from modules.operations.taskings.data.lookups import (
            CATEGORIES,
            PRIORITIES,
            TASK_STATUSES,
            TASK_TYPES_BY_CATEGORY,
            TEAM_STATUS_BY_CATEGORY,
        )
        from utils.constants import RADIO_TASK_FUNCTIONS

        return {
            "categories": list(CATEGORIES),
            "priorities": list(PRIORITIES),
            "task_statuses": list(TASK_STATUSES),
            "task_types_by_category": dict(TASK_TYPES_BY_CATEGORY),
            "team_status_by_category": dict(TEAM_STATUS_BY_CATEGORY),
            "radio_functions": list(RADIO_TASK_FUNCTIONS),
        }

    @Slot(int, result="QVariant")
    def getTaskDetail(self, task_id: int) -> Any:  # noqa: N802
        # Use incident DB repository
        from modules.operations.taskings.repository import get_task_detail

        detail = get_task_detail(task_id)
        return _to_variant(detail)

    @Slot(int, "QVariant", result=bool)
    def updateTaskHeader(self, task_id: int, payload: Any) -> bool:  # noqa: N802
        from modules.operations.taskings.repository import update_task_header
        try:
            update_task_header(int(task_id), dict(payload or {}))
            return True
        except Exception:
            return False

    @Slot(int, result="QVariant")
    def listNarrative(self, task_id: int) -> Any:  # noqa: N802
        # Use incident DB via IncidentBridge (handles different table names)
        from bridge.incident_bridge import IncidentBridge

        ib = IncidentBridge()
        rows = ib.listTaskNarrative(task_id, "", False, "")
        return {"entries": rows}

    @Slot(int, "QVariant", result="QVariant")
    def addNarrative(self, task_id: int, payload: Any) -> Any:  # noqa: N802
        from bridge.incident_bridge import IncidentBridge

        ib = IncidentBridge()
        data = dict(payload or {})
        # Default entered_by to the current signed-in user id if not provided
        try:
            from utils.state import AppState
            current_uid = AppState.get_active_user_id()
        except Exception:
            current_uid = None
        # Map common keys to DB schema
        mapped = {
            "taskid": int(task_id),
            "timestamp": data.get("timestamp"),
            "narrative": data.get("entry_text") or data.get("text") or "",
            "entered_by": data.get("entered_by") or data.get("by") or (int(current_uid) if current_uid is not None else ""),
            "team_num": data.get("team_name") or data.get("team") or "",
            "critical": 1 if data.get("critical_flag") else 0,
        }
        new_id = ib.createTaskNarrative(mapped)
        mapped["id"] = new_id
        # Return in the shape QML expects
        return {
            "id": new_id,
            "timestamp": mapped["timestamp"],
            "entry_text": mapped["narrative"],
            "entered_by": mapped["entered_by"],
            "team_name": mapped["team_num"],
            "critical_flag": bool(mapped["critical"]),
        }

    @Slot(int, int, result=bool)
    def deleteNarrative(self, task_id: int, entry_id: int) -> bool:  # noqa: N802
        from bridge.incident_bridge import IncidentBridge
        try:
            ib = IncidentBridge()
            return bool(ib.deleteTaskNarrative(int(entry_id)))
        except Exception:
            return False

    @Slot("QString", bool, result=bool)
    def addIcs214Entry(self, text: str, critical_flag: bool = False) -> bool:  # noqa: N802
        """Append a simple entry to the default ICS-214 stream for the active incident.

        Creates a default Operations stream if none exists.
        """
        try:
            from utils import incident_context
            from utils.state import AppState
            from modules.ics214 import services
            from modules.ics214.schemas import StreamCreate, EntryCreate
        except Exception:
            return False

        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return False
        # Find or create a default stream (Operations Unit Log)
        streams = services.list_streams(incident_id)
        stream = None
        for s in streams:
            try:
                if getattr(s, "name", "") == "Operations Unit Log":
                    stream = s
                    break
            except Exception:
                continue
        if stream is None:
            stream = services.create_stream(StreamCreate(incident_id=incident_id, name="Operations Unit Log", section="Operations"))

        uid = AppState.get_active_user_id()
        try:
            services.add_entry(
                incident_id,
                stream.id,  # type: ignore[attr-defined]
                EntryCreate(text=str(text or ""), critical_flag=bool(critical_flag), actor_user_id=str(uid) if uid is not None else None),
            )
            return True
        except Exception:
            return False

    @Slot(int, result="QVariant")
    def listTeams(self, task_id: int) -> Any:  # noqa: N802
        from modules.operations.taskings.repository import list_task_teams

        teams = list_task_teams(task_id)
        return {"teams": [_to_variant(t) for t in teams]}

    @Slot(int, result="QVariant")
    def listPersonnel(self, task_id: int) -> Any:  # noqa: N802
        from modules.operations.taskings.repository import list_task_personnel
        rows = list_task_personnel(int(task_id))
        return {"people": _to_variant(rows)}

    @Slot(int, result="QVariant")
    def listVehicles(self, task_id: int) -> Any:  # noqa: N802
        from modules.operations.taskings.repository import list_task_vehicles
        rows = list_task_vehicles(int(task_id))
        return {"vehicles": _to_variant(rows)}

    @Slot(int, result="QVariant")
    def listAircraft(self, task_id: int) -> Any:  # noqa: N802
        from modules.operations.taskings.repository import list_task_aircraft
        rows = list_task_aircraft(int(task_id))
        return {"aircraft": _to_variant(rows)}

    # Communications --------------------------------------------------------
    @Slot(result="QVariant")
    def listCommsChannels(self) -> Any:  # noqa: N802
        from modules.operations.taskings.repository import list_incident_channels
        return {"channels": list_incident_channels()}

    @Slot(int, result="QVariant")
    def listTaskComms(self, task_id: int) -> Any:  # noqa: N802
        from modules.operations.taskings.repository import list_task_comms
        return {"rows": list_task_comms(int(task_id))}

    @Slot(int, "QVariant", result="QVariant")
    def addTaskComm(self, task_id: int, payload: Any) -> Any:  # noqa: N802
        from modules.operations.taskings.repository import add_task_comm, list_task_comms
        data = dict(payload or {})
        row_id = add_task_comm(int(task_id), data.get("incident_channel_id"), data.get("function"), data.get("remarks"))
        return {"added_id": row_id, "rows": list_task_comms(int(task_id))}

    @Slot(int, "QVariant", result=bool)
    def updateTaskComm(self, row_id: int, payload: Any) -> bool:  # noqa: N802
        from modules.operations.taskings.repository import update_task_comm
        try:
            data = dict(payload or {})
            update_task_comm(int(row_id), data.get("incident_channel_id"), data.get("function"))
            return True
        except Exception:
            return False

    @Slot(int, result=bool)
    def removeTaskComm(self, row_id: int) -> bool:  # noqa: N802
        from modules.operations.taskings.repository import remove_task_comm
        try:
            remove_task_comm(int(row_id))
            return True
        except Exception:
            return False

    # Debriefing ------------------------------------------------------------
    @Slot(int, result="QVariant")
    def listDebriefs(self, task_id: int) -> Any:  # noqa: N802
        from modules.operations.taskings.repository import list_task_debriefs
        return {"rows": list_task_debriefs(int(task_id))}

    @Slot(int, "QVariant", result="QVariant")
    def createDebrief(self, task_id: int, payload: Any) -> Any:  # noqa: N802
        from modules.operations.taskings.repository import create_debrief, list_task_debriefs
        data = dict(payload or {})
        types = data.get("types") or []
        debrief_id = create_debrief(int(task_id), str(data.get("sortie_number") or ""), str(data.get("debriefer_id") or ""), list(types))
        return {"created_id": debrief_id, "rows": list_task_debriefs(int(task_id))}

    @Slot(int, result="QVariant")
    def getDebrief(self, debrief_id: int) -> Any:  # noqa: N802
        from modules.operations.taskings.repository import get_debrief
        return _to_variant(get_debrief(int(debrief_id)))

    @Slot(int, "QString", "QVariant", result=bool)
    def saveDebriefForm(self, debrief_id: int, form_key: str, payload: Any) -> bool:  # noqa: N802
        from modules.operations.taskings.repository import save_debrief_form
        try:
            save_debrief_form(int(debrief_id), str(form_key), dict(payload or {}))
            return True
        except Exception:
            return False

    @Slot(int, "QVariant", result=bool)
    def updateDebriefHeader(self, debrief_id: int, payload: Any) -> bool:  # noqa: N802
        from modules.operations.taskings.repository import update_debrief_header
        try:
            update_debrief_header(int(debrief_id), dict(payload or {}))
            return True
        except Exception:
            return False

    @Slot(int, result="QVariant")
    def submitDebrief(self, debrief_id: int) -> Any:  # noqa: N802
        """Set debrief status to Submitted and flag for review; return updated header."""
        from modules.operations.taskings.repository import update_debrief_header, get_debrief
        from datetime import datetime
        try:
            from utils.state import AppState
            uid = AppState.get_active_user_id()
        except Exception:
            uid = None
        now = datetime.utcnow().isoformat()
        update_debrief_header(int(debrief_id), {"status": "Submitted", "flagged_for_review": 1, "submitted_by": str(uid) if uid is not None else None, "submitted_at": now})
        # Audit hook for planning review
        try:
            from utils.audit import write_audit
            d = get_debrief(int(debrief_id))
            write_audit("debrief.submitted", {"debrief_id": int(debrief_id), "task_id": d.get("task_id")}, prefer_mission=True)
        except Exception:
            pass
        return _to_variant(get_debrief(int(debrief_id)))

    @Slot(int, result="QVariant")
    def markDebriefReviewed(self, debrief_id: int) -> Any:  # noqa: N802
        from modules.operations.taskings.repository import update_debrief_header, get_debrief
        from datetime import datetime
        try:
            from utils.state import AppState
            uid = AppState.get_active_user_id()
        except Exception:
            uid = None
        now = datetime.utcnow().isoformat()
        update_debrief_header(int(debrief_id), {"status": "Reviewed", "flagged_for_review": 0, "reviewed_by": str(uid) if uid is not None else None, "reviewed_at": now})
        try:
            from utils.audit import write_audit
            d = get_debrief(int(debrief_id))
            write_audit("debrief.reviewed", {"debrief_id": int(debrief_id), "task_id": d.get("task_id")}, prefer_mission=True)
        except Exception:
            pass
        return _to_variant(get_debrief(int(debrief_id)))

    @Slot(int, result="QVariant")
    def archiveDebrief(self, debrief_id: int) -> Any:  # noqa: N802
        from modules.operations.taskings.repository import archive_debrief, get_debrief
        archive_debrief(int(debrief_id))
        return _to_variant(get_debrief(int(debrief_id)))

    @Slot(int, int, result="QVariant")
    def deleteDebrief(self, task_id: int, debrief_id: int) -> Any:  # noqa: N802
        from modules.operations.taskings.repository import delete_debrief, list_task_debriefs
        delete_debrief(int(debrief_id))
        return {"rows": list_task_debriefs(int(task_id))}

    # Log/Audit --------------------------------------------------------------
    @Slot(int, "QVariant", result="QVariant")
    def listAudit(self, task_id: int, filters: Any) -> Any:  # noqa: N802
        from modules.operations.taskings.repository import list_audit_logs
        f = dict(filters or {})
        rows = list_audit_logs(
            int(task_id) if task_id > 0 else None,
            str(f.get("search", "")),
            f.get("from"),
            f.get("to"),
            str(f.get("field", "")),
            int(f.get("limit", 500)),
        )
        return {"rows": rows}

    @Slot(int, "QVariant", result="QString")
    def exportAudit(self, task_id: int, filters: Any) -> str:  # noqa: N802
        from modules.operations.taskings.repository import export_audit_csv
        f = dict(filters or {})
        return export_audit_csv(
            int(task_id) if task_id > 0 else None,
            str(f.get("search", "")),
            f.get("from"),
            f.get("to"),
            str(f.get("field", "")),
        )

    @Slot(int, result="QVariant")
    def getAssignment(self, task_id: int) -> Any:  # noqa: N802
        from modules.operations.taskings.repository import get_task_assignment
        data = get_task_assignment(int(task_id))
        return _to_variant(data)

    @Slot(int, "QVariant", result="QVariant")
    def saveAssignment(self, task_id: int, payload: Any) -> Any:  # noqa: N802
        from modules.operations.taskings.repository import save_task_assignment
        data = save_task_assignment(int(task_id), dict(payload or {}))
        return _to_variant(data)

    @Slot(int, "QVariant", result="QVariant")
    def exportForms(self, task_id: int, forms: Any) -> Any:  # noqa: N802
        from modules.operations.taskings.repository import export_assignment_forms
        lst = forms if isinstance(forms, (list, tuple)) else [forms]
        result = export_assignment_forms(int(task_id), [str(x) for x in lst])
        return _to_variant(result)

    @Slot(int, "QVariant", result="QVariant")
    def addTeam(self, task_id: int, payload: Any) -> Any:  # noqa: N802
        """Assign a team to a task. Payload may include 'team_id', 'sortie_number', 'primary'."""
        from modules.operations.taskings.repository import add_task_team, list_task_teams

        data = dict(payload or {})
        team_id = data.get("team_id")
        sortie = data.get("sortie_number") or data.get("sortie_id")
        primary = bool(data.get("primary", False))
        tt_id = add_task_team(int(task_id), int(team_id) if team_id is not None else None, str(sortie) if sortie else None, primary)
        # Return fresh list
        teams = list_task_teams(int(task_id))
        return {"added_id": tt_id, "teams": [_to_variant(t) for t in teams]}

    # Note: No separate narrative dialog; handled inside Task Detail window.

    @Slot(result="QVariant")
    def listAllTeams(self) -> Any:  # noqa: N802
        from modules.operations.taskings.repository import list_all_teams
        return {"teams": list_all_teams()}

    @Slot(int, int, result="QVariant")
    def setPrimary(self, task_id: int, tt_id: int) -> Any:  # noqa: N802
        from modules.operations.taskings.repository import set_primary_team, list_task_teams
        set_primary_team(int(task_id), int(tt_id))
        teams = list_task_teams(int(task_id))
        return {"teams": [_to_variant(t) for t in teams]}

    @Slot(int, "QString", result=bool)
    def updateSortie(self, tt_id: int, sortie_id: str) -> bool:  # noqa: N802
        from modules.operations.taskings.repository import update_sortie_id
        try:
            update_sortie_id(int(tt_id), str(sortie_id))
            return True
        except Exception:
            return False

    @Slot(int, result=bool)
    def removeTeam(self, tt_id: int) -> bool:  # noqa: N802
        from modules.operations.taskings.repository import remove_task_team
        try:
            remove_task_team(int(tt_id))
            return True
        except Exception:
            return False

    @Slot(int, "QString", result=bool)
    def changeTeamStatus(self, tt_id: int, status_label: str) -> bool:  # noqa: N802
        """Change assignment status for a task_teams row using a human label.

        Maps common human labels to repository keys and stamps the first time only.
        """
        from modules.operations.data.repository import set_team_assignment_status
        key = str(status_label or "").strip().lower()
        # Normalize a few label variants
        key = {
            "en route": "enroute",
            "on scene": "arrival",
            "discovery/find": "discovery",
            "find": "discovery",
            "rtb": "returning",
        }.get(key, key)
        try:
            set_team_assignment_status(int(tt_id), key)
            return True
        except Exception:
            return False

    @Slot(int)
    def openTeamDetail(self, team_id: int) -> None:  # noqa: N802
        try:
            from modules.operations.teams.windows import open_team_detail_window
            open_team_detail_window(int(team_id))
        except Exception:
            # Non-fatal in case the window implementation is unavailable
            pass
