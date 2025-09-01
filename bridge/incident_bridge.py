from __future__ import annotations

from typing import Any, Dict, List, Optional
import sqlite3

from PySide6.QtCore import QObject, Slot

from utils import incident_context


def _dict_factory(cursor: sqlite3.Cursor, row: tuple) -> Dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


class IncidentBridge(QObject):
    """QObject bridge for incident-scoped data in the active incident DB.

    Currently implements CRUD for the narrative entries table.
    """

    # --- Utilities ---------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        db_path = incident_context.get_active_incident_db_path()
        con = sqlite3.connect(str(db_path))
        con.row_factory = _dict_factory
        return con

    def _ensure_narrative_table(self) -> None:
        """Ensure a narrative table exists; prefer 'task_narrative', else use
        existing 'narrative_entries'. Create 'task_narrative' if neither exists.
        """
        try:
            with self._connect() as con:
                cur = con.execute("SELECT name FROM sqlite_master WHERE type='table'")
                names = {r["name"] for r in cur.fetchall()}
                if "task_narrative" in names or "narrative_entries" in names:
                    return
                con.execute(
                    """
                    CREATE TABLE task_narrative (
                        id INTEGER PRIMARY KEY,
                        taskid INTEGER NOT NULL,
                        timestamp TEXT NOT NULL,
                        narrative TEXT NOT NULL,
                        entered_by INTEGER NOT NULL,
                        team_num TEXT,
                        critical INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                con.commit()
        except Exception:
            # best-effort; table may already exist or DB locked
            pass

    def _narrative_table(self) -> str:
        with self._connect() as con:
            cur = con.execute("SELECT name FROM sqlite_master WHERE type='table'")
            names = {r["name"] for r in cur.fetchall()}
        return "task_narrative" if "task_narrative" in names else "narrative_entries"

    # --- Narrative CRUD ----------------------------------------------------
    @Slot(int, str, bool, str, result=list)
    def listTaskNarrative(self, taskId: int = 0, searchText: str = "", criticalOnly: bool = False, teamFilter: str = "") -> List[Dict[str, Any]]:
        """List narrative for a task (or all tasks if taskId==0)."""
        self._ensure_narrative_table()
        table = self._narrative_table()
        where = []
        params: List[Any] = []
        if taskId:
            where.append("taskid = ?")
            params.append(taskId)
        if searchText:
            where.append("(narrative LIKE ? OR entered_by LIKE ?)")
            params.extend([f"%{searchText}%", f"%{searchText}%"])
        if criticalOnly:
            where.append("critical = 1")
        if teamFilter:
            where.append("team_num = ?")
            params.append(teamFilter)
        wh = (" WHERE " + " AND ".join(where)) if where else ""
        sql = f"SELECT id, taskid, timestamp, narrative, entered_by, team_num, critical FROM {table}{wh} ORDER BY timestamp DESC"
        try:
            with self._connect() as con:
                cur = con.execute(sql, params)
                rows = cur.fetchall()
                try:
                    print(f"[IncidentBridge.listTaskNarrative] {len(rows)} rows from {table}")
                except Exception:
                    pass
                return rows
        except Exception as e:
            print("[IncidentBridge.listTaskNarrative]", e)
            return []

    @Slot(dict, result=int)
    def createTaskNarrative(self, data: Dict[str, Any]) -> int:
        self._ensure_narrative_table()
        table = self._narrative_table()
        cols = ["taskid", "timestamp", "narrative", "entered_by", "team_num", "critical"]
        vals = [data.get(k) for k in cols]
        placeholders = ",".join(["?"] * len(cols))
        sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
        try:
            with self._connect() as con:
                cur = con.execute(sql, vals)
                con.commit()
                return int(cur.lastrowid)
        except Exception as e:
            print("[IncidentBridge.createTaskNarrative]", e)
            return 0

    @Slot(int, dict, result=bool)
    def updateTaskNarrative(self, id_value: int, data: Dict[str, Any]) -> bool:
        table = self._narrative_table()
        allowed = {"timestamp", "narrative", "entered_by", "team_num", "critical"}
        cols = [k for k in data.keys() if k in allowed]
        if not cols:
            return False
        set_clause = ", ".join([f"{c}=?" for c in cols])
        sql = f"UPDATE {table} SET {set_clause} WHERE id=?"
        try:
            with self._connect() as con:
                con.execute(sql, [data.get(c) for c in cols] + [id_value])
                con.commit()
                return True
        except Exception as e:
            print("[IncidentBridge.updateTaskNarrative]", e)
            return False

    @Slot(int, result=bool)
    def deleteTaskNarrative(self, id_value: int) -> bool:
        table = self._narrative_table()
        try:
            with self._connect() as con:
                con.execute(f"DELETE FROM {table} WHERE id=?", (id_value,))
                con.commit()
                return True
        except Exception as e:
            print("[IncidentBridge.deleteTaskNarrative]", e)
            return False

    # --- Exports ------------------------------------------------------------
    @Slot(int, result=bool)
    def exportIcs214(self, taskId: int = 0) -> bool:
        """Stub exporter: writes a CSV with narrative entries for a task/all.
        Returns True on success. Real 214 PDF generation can be added later.
        """
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
                    line = [str(r.get("id","")), str(r.get("timestamp","")), str(r.get("entered_by","")), str(r.get("team_num","")), str(r.get("critical","")), '"'+str(r.get("narrative","")) .replace('"','""')+'"']
                    f.write(",".join(line) + "\n")
            print(f"[IncidentBridge.exportIcs214] wrote {len(rows)} rows to {p}")
            return True
        except Exception as e:
            print("[IncidentBridge.exportIcs214]", e)
            return False
