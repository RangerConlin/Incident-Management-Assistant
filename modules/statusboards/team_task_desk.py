"""Team/Task Newsroom Desk.

Stitches the raw `teams` and `tasks` collections in `incident_cache` into the
same summary rows the Team Status and Task Status boards display — the join
that used to live entirely server-side in
`data/db/sarapp_db/api/routers/operations.py` (`team-assignment-rows`,
`task-rows`). Boards read from this desk instead of polling those endpoints
and instead of touching `incident_cache` directly.

NOTE: as of this writing, `operations.py` does not yet broadcast changes to
`teams`/`tasks` over the WebSocket (it predates `BaseRepository`), and those
collections' documents lack the `deleted` field the snapshot endpoint filters
on — so this desk will not see any team/task data, live or otherwise, until
that router is retrofitted. The join logic here is written to be correct
once that happens.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from PySide6.QtCore import QObject, Signal

from utils.incident_cache import incident_cache

logger = logging.getLogger(__name__)

_PRIORITY_MAP = {1: "Low", 2: "Medium", 3: "High", 4: "Critical"}
_STATUS_LABEL = {
    "completed": "complete", "complete": "complete", "draft": "created", "created": "created",
    "planned": "planned", "assigned": "assigned", "in progress": "in progress", "cancelled": "cancelled",
}
_TEAM_STATUS_RELABEL = {"en route": "enroute", "on scene": "arrival", "rtb": "returning"}

_TEAMS_COLLECTION = "teams"
_TASKS_COLLECTION = "tasks"
_PERSONNEL_COLLECTION = "incident_personnel"
_PROFILE_COLLECTION = "incident_profile"

_WATCHED_COLLECTIONS = {_TEAMS_COLLECTION, _TASKS_COLLECTION, _PERSONNEL_COLLECTION, _PROFILE_COLLECTION}


def _resolve_leader(team_doc: dict[str, Any], personnel_by_master_id: dict[Any, dict[str, Any]]) -> tuple[str, str]:
    leader_name = team_doc.get("leader_name") or ""
    leader_phone = team_doc.get("leader_phone") or team_doc.get("phone") or ""
    pid = team_doc.get("leader_personnel_id") or team_doc.get("team_leader")
    if pid and (not leader_name or not leader_phone):
        try:
            person = personnel_by_master_id.get(int(pid))
        except (TypeError, ValueError):
            person = None
        if person:
            if not leader_name:
                leader_name = person.get("name") or (
                    ((person.get("first_name") or "") + " " + (person.get("last_name") or "")).strip()
                )
            if not leader_phone:
                leader_phone = person.get("phone") or ""
    return leader_name, leader_phone


class TeamTaskDesk(QObject):
    """Builds and keeps current the Team Status / Task Status board rows.

    `team_rows_changed` and `task_rows_changed` fire with the full current
    row list whenever anything affecting that board changes — boards are
    expected to just re-render from the given list, not diff it themselves.
    """

    team_rows_changed = Signal(list)
    task_rows_changed = Signal(list)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._team_rows: list[dict[str, Any]] = []
        self._task_rows: list[dict[str, Any]] = []
        incident_cache.changed.connect(self._on_cache_changed)
        incident_cache.snapshotLoaded.connect(self._on_snapshot_loaded)
        self._rebuild()

    # ------------------------------------------------------------------
    # Public reads
    # ------------------------------------------------------------------

    def team_rows(self) -> list[dict[str, Any]]:
        return list(self._team_rows)

    def task_rows(self) -> list[dict[str, Any]]:
        return list(self._task_rows)

    # ------------------------------------------------------------------
    # Cache reactions
    # ------------------------------------------------------------------

    def _on_snapshot_loaded(self) -> None:
        self._rebuild()

    def _on_cache_changed(self, collection: str, op: str, doc_id: str) -> None:
        if collection in _WATCHED_COLLECTIONS:
            self._rebuild()

    # ------------------------------------------------------------------
    # Join logic — ported from operations.py's team-assignment-rows /
    # task-rows endpoints, reading cached documents instead of Mongo.
    # ------------------------------------------------------------------

    def _rebuild(self) -> None:
        try:
            teams = incident_cache.get_all(_TEAMS_COLLECTION)
            tasks = incident_cache.get_all(_TASKS_COLLECTION)
            personnel = incident_cache.get_all(_PERSONNEL_COLLECTION)
            profiles = incident_cache.get_all(_PROFILE_COLLECTION)
        except Exception:
            logger.exception("TeamTaskDesk failed to read incident_cache")
            return

        tasks_by_int_id = {t.get("int_id"): t for t in tasks if t.get("int_id") is not None}
        tasks_by_task_id = {t.get("task_id"): t for t in tasks if t.get("task_id")}
        personnel_by_master_id: dict[Any, dict[str, Any]] = {}
        for person in personnel:
            master_id = person.get("master_id")
            if master_id is not None:
                try:
                    personnel_by_master_id[int(master_id)] = person
                except (TypeError, ValueError):
                    pass
        incident_created_at = None
        if profiles:
            incident_created_at = profiles[0].get("created_at") or profiles[0].get("updated_at")

        self._team_rows = self._build_team_rows(teams, tasks_by_int_id, tasks_by_task_id, personnel_by_master_id, incident_created_at)
        self._task_rows = self._build_task_rows(tasks, teams)
        self.team_rows_changed.emit(self.team_rows())
        self.task_rows_changed.emit(self.task_rows())

    def _build_team_rows(
        self,
        teams: list[dict[str, Any]],
        tasks_by_int_id: dict[Any, dict[str, Any]],
        tasks_by_task_id: dict[Any, dict[str, Any]],
        personnel_by_master_id: dict[Any, dict[str, Any]],
        incident_created_at: Any,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for team in sorted(teams, key=lambda t: t.get("int_id") or 0):
            team_int_id = team.get("int_id")
            team_str_id = team.get("team_id") or str(team_int_id)
            current_task_ref = team.get("current_task_id")
            assignment = ""
            task_location = ""
            sortie_display = ""
            if current_task_ref is not None:
                task = (
                    tasks_by_task_id.get(current_task_ref)
                    if isinstance(current_task_ref, str)
                    else tasks_by_int_id.get(current_task_ref)
                )
                if task:
                    task_number = task.get("task_id") or ""
                    task_title = task.get("title") or ""
                    if task_number and task_title:
                        assignment = f"{task_number} - {task_title}"
                    else:
                        assignment = task_number or task_title
                    task_location = task.get("location") or ""
                    for tt in reversed(task.get("task_teams") or task.get("assigned_teams") or []):
                        ref = tt.get("team_id")
                        if ref == team_str_id or ref == team_int_id:
                            sortie_display = tt.get("sortie_id") or ""
                            break
            leader_name, leader_phone = _resolve_leader(team, personnel_by_master_id)
            status = str(team.get("status") or "available").strip().lower()
            status = _TEAM_STATUS_RELABEL.get(status, status)
            location = team.get("location") or task_location or ""
            team_type = str(team.get("team_type") or "").upper()
            is_aircraft = team_type == "AIR"
            display_name = (team.get("callsign") if is_aircraft else None) or team.get("name") or f"Team {team_int_id}"
            rows.append({
                "tt_id": None,
                "task_id": current_task_ref,
                "team_id": team_int_id,
                "sortie": sortie_display,
                "name": display_name,
                "team_type": team_type,
                "leader": leader_name,
                "contact": leader_phone,
                "status": status,
                "assignment": assignment,
                "location": location,
                "needs_attention": bool(team.get("needs_attention")),
                "needs_assistance_flag": bool(team.get("needs_attention")),
                "emergency_flag": bool(team.get("emergency_flag")),
                "last_checkin_at": team.get("last_checkin_at"),
                "checkin_reference_at": team.get("checkin_reference_at") or team.get("last_checkin_at") or team.get("created_at") or incident_created_at,
                "team_status_updated": team.get("status_updated"),
                "last_updated": team.get("last_checkin_at") or team.get("status_updated") or team.get("created_at") or incident_created_at,
            })
        return rows

    def _build_task_rows(self, tasks: list[dict[str, Any]], teams: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for doc in sorted(tasks, key=lambda t: t.get("int_id") or 0):
            task_int_id = doc.get("int_id")
            task_str_id = doc.get("task_id") or str(task_int_id)
            active_ids = doc.get("active_team_ids")
            if active_ids is not None:
                matching_teams = [
                    team for team in teams
                    if team.get("int_id") in active_ids or team.get("team_id") in active_ids
                ]
            else:
                matching_teams = [
                    team for team in teams
                    if team.get("current_task_id") in (task_int_id, task_str_id)
                ]
            assigned = []
            for team in matching_teams:
                sortie_id = None
                for tt in reversed(doc.get("task_teams") or doc.get("assigned_teams") or []):
                    if tt.get("team_id") in (team.get("int_id"), team.get("team_id")):
                        sortie_id = tt.get("sortie_id")
                        break
                assigned.append(team.get("name") or sortie_id or f"Team {team.get('int_id')}")
            priority = doc.get("priority", "")
            try:
                priority = _PRIORITY_MAP.get(int(priority), str(priority))
            except (ValueError, TypeError):
                pass
            rows.append({
                "id": task_int_id,
                "number": doc.get("task_id") or f"T-{task_int_id}",
                "name": doc.get("title") or "",
                "assigned_teams": assigned,
                "status": _STATUS_LABEL.get(str(doc.get("status") or "").lower(), str(doc.get("status") or "").lower()),
                "priority": priority,
                "location": doc.get("location") or "",
            })
        return rows


_DESK: Optional[TeamTaskDesk] = None


def get_team_task_desk() -> TeamTaskDesk:
    global _DESK
    if _DESK is None:
        _DESK = TeamTaskDesk()
    return _DESK


__all__ = ["TeamTaskDesk", "get_team_task_desk"]
