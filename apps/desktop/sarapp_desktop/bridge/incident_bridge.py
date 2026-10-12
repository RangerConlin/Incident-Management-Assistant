"""QObject bridge for incident task narrative entries.

All reads and writes go through the API server (POST/PATCH/DELETE
/api/incidents/{id}/narratives backed by MongoDB).  The SQLite
incident.db is no longer touched by this bridge.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Slot

from utils import incident_context


class IncidentBridge(QObject):
    """QObject bridge for incident-scoped narrative CRUD."""

    def _incident_id(self) -> Optional[str]:
        return incident_context.get_active_incident_id()

    # --- Narrative CRUD ----------------------------------------------------

    def _cached_narratives(
        self,
        incident_id: str,
        task_id: int,
        search_text: str,
        critical_only: bool,
        team_filter: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """Return the embedded narrative from IncidentCache when available."""
        try:
            from utils.incident_cache import incident_cache

            if incident_cache.incident_id != incident_id:
                return None
            tasks = incident_cache.get_all("tasks")
            if not tasks:
                return None
            personnel = incident_cache.get_all("incident_personnel")
        except Exception:
            return None

        names: dict[str, str] = {}
        for person in personnel:
            person_record = person.get("person_record")
            if person_record is None:
                person_record = person.get("master_id")
            if person_record is None:
                continue
            name = person.get("name") or (
                f"{person.get('first_name') or ''} {person.get('last_name') or ''}".strip()
            )
            names[str(person_record)] = str(name or "")

        needle = str(search_text or "").lower()
        rows: List[Dict[str, Any]] = []
        matched_task = False
        for task in tasks:
            current_task_id = int(task.get("int_id") or 0)
            if task_id and current_task_id != int(task_id):
                continue
            matched_task = True
            for entry in task.get("narrative") or []:
                row = dict(entry)
                row["id"] = str(row.get("id") or row.get("entry_id") or "")
                row["task_id"] = int(row.get("task_id") or current_task_id)
                row["timestamp"] = str(row.get("timestamp") or row.get("ts_utc") or "")
                row["narrative"] = str(
                    row.get("narrative") or row.get("text") or row.get("entry_text") or ""
                )
                row["entered_by"] = str(
                    row.get("entered_by")
                    or row.get("author_user_id")
                    or row.get("author_display_name")
                    or ""
                )
                row["entered_by_display"] = names.get(row["entered_by"], "")
                row["team_num"] = str(
                    row.get("team_num") or row.get("team") or row.get("team_name") or ""
                )
                row["critical"] = (
                    1 if row.get("critical") in (True, 1, "1", "true", "True") else 0
                )
                if critical_only and not row["critical"]:
                    continue
                if team_filter and row["team_num"] != str(team_filter):
                    continue
                if (
                    needle
                    and needle not in row["narrative"].lower()
                    and needle not in row["entered_by"].lower()
                ):
                    continue
                rows.append(row)
        if task_id and not matched_task:
            return None
        rows.sort(key=lambda row: row.get("timestamp") or "", reverse=True)
        return rows

    @Slot(int, str, bool, str, result=list)
    def listTaskNarrative(
        self,
        taskId: int = 0,
        searchText: str = "",
        criticalOnly: bool = False,
        teamFilter: str = "",
    ) -> List[Dict[str, Any]]:
        iid = self._incident_id()
        if not iid:
            return []
        try:
            from utils.api_client import api_client
            cached = self._cached_narratives(
                iid,
                taskId,
                searchText,
                criticalOnly,
                teamFilter,
            )
            if cached is not None:
                return cached
            params: dict[str, Any] = {}
            if taskId:
                params["task_id"] = taskId
            if searchText:
                params["search"] = searchText
            if criticalOnly:
                params["critical_only"] = True
            if teamFilter:
                params["team"] = teamFilter
            return api_client.get(f"/api/incidents/{iid}/narratives", params=params) or []
        except Exception as exc:
            print("[IncidentBridge.listTaskNarrative]", exc)
            return []

    @Slot(dict, result=str)
    def createTaskNarrative(self, data: Dict[str, Any]) -> str:
        iid = self._incident_id()
        if not iid:
            return ""
        try:
            from utils.api_client import api_client
            payload = {
                "task_id": int(data.get("taskid") or 0),
                "timestamp": str(data.get("timestamp") or ""),
                "narrative": str(data.get("narrative") or ""),
                "entered_by": str(data.get("entered_by") or ""),
                "team_num": str(data.get("team_num") or ""),
                "critical": int(data.get("critical") or 0),
            }
            result = api_client.post(f"/api/incidents/{iid}/narratives", json=payload)
            return str(result.get("id", "")) if result else ""
        except Exception as exc:
            print("[IncidentBridge.createTaskNarrative]", exc)
            return ""

    @Slot(str, dict, result=bool)
    def updateTaskNarrative(self, entry_id: str, data: Dict[str, Any]) -> bool:
        iid = self._incident_id()
        if not iid or not entry_id:
            return False
        allowed = {"timestamp", "narrative", "entered_by", "team_num", "critical"}
        payload = {k: v for k, v in data.items() if k in allowed}
        if not payload:
            return False
        try:
            from utils.api_client import api_client
            api_client.patch(f"/api/incidents/{iid}/narratives/{entry_id}", json=payload)
            return True
        except Exception as exc:
            print("[IncidentBridge.updateTaskNarrative]", exc)
            return False

    @Slot(str, result=bool)
    def deleteTaskNarrative(self, entry_id: str) -> bool:
        iid = self._incident_id()
        if not iid or not entry_id:
            return False
        try:
            from utils.api_client import api_client
            api_client.delete(f"/api/incidents/{iid}/narratives/{entry_id}")
            return True
        except Exception as exc:
            print("[IncidentBridge.deleteTaskNarrative]", exc)
            return False

    # --- Exports ------------------------------------------------------------

    @Slot(int, result=bool)
    def exportIcs214(self, taskId: int = 0) -> bool:
        """Write a CSV with narrative entries for a task (or all tasks)."""
        rows = self.listTaskNarrative(taskId, "", False, "")
        try:
            from pathlib import Path
            out_dir = Path("data") / "exports"
            out_dir.mkdir(parents=True, exist_ok=True)
            name = f"ics214_narrative_{taskId or 'all'}.csv"
            p = out_dir / name
            with p.open("w", encoding="utf-8") as f:
                f.write("id,timestamp,entered_by,team_num,critical,narrative\n")
                for r in rows:
                    line = [
                        str(r.get("id", "")),
                        str(r.get("timestamp", "")),
                        str(r.get("entered_by", "")),
                        str(r.get("team_num", "")),
                        str(r.get("critical", "")),
                        '"' + str(r.get("narrative", "")).replace('"', '""') + '"',
                    ]
                    f.write(",".join(line) + "\n")
            return True
        except Exception as exc:
            print("[IncidentBridge.exportIcs214]", exc)
            return False
