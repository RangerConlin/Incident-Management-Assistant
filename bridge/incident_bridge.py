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
            params: dict[str, Any] = {}
            if taskId:
                params["task_id"] = taskId
            if searchText:
                params["search"] = searchText
            if criticalOnly:
                params["critical_only"] = True
            if teamFilter:
                params["team"] = teamFilter
            rows = api_client.get(f"/api/incidents/{iid}/narratives", params=params) or []
            # Resolve entered_by to a display name when it looks like a numeric id
            try:
                from modules.logistics.checkin import repository as ci_repo
                names_cache: dict[str, str] = {}
                for r in rows:
                    eb = r.get("entered_by")
                    r["entered_by_display"] = eb
                    try:
                        uid = int(eb)
                    except Exception:
                        continue
                    key = str(uid)
                    if key in names_cache:
                        r["entered_by_display"] = names_cache[key]
                    else:
                        try:
                            ident = ci_repo.get_person_identity(str(uid))
                            disp = ident.name if ident and ident.name else key
                        except Exception:
                            disp = key
                        names_cache[key] = disp
                        r["entered_by_display"] = disp
            except Exception:
                pass
            return rows
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
