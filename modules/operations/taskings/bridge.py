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
        )

        return {
            "categories": list(CATEGORIES),
            "priorities": list(PRIORITIES),
            "task_statuses": list(TASK_STATUSES),
        }

    @Slot(int, result="QVariant")
    def getTaskDetail(self, task_id: int) -> Any:  # noqa: N802
        # Use incident DB repository
        from modules.operations.taskings.repository import get_task_detail

        detail = get_task_detail(task_id)
        return _to_variant(detail)

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
        # Map common keys to DB schema
        mapped = {
            "taskid": int(task_id),
            "timestamp": data.get("timestamp"),
            "narrative": data.get("entry_text") or data.get("text") or "",
            "entered_by": data.get("entered_by") or data.get("by") or "",
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

    @Slot(int, result="QVariant")
    def listTeams(self, task_id: int) -> Any:  # noqa: N802
        from modules.operations.taskings.repository import list_task_teams

        teams = list_task_teams(task_id)
        return {"teams": [_to_variant(t) for t in teams]}

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
