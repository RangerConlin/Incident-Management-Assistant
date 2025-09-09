from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from PySide6.QtCore import QObject, Slot, Signal, Property

from modules.planning.models.objectives_models import ObjectiveListModel, SimpleListModel

UTC = timezone.utc
STATUS_VALUES = ["Pending", "Approved", "Assigned", "In Progress", "Completed", "Cancelled"]
PRIORITY_VALUES = ["Low", "Normal", "High", "Urgent"]


class ObjectiveBridge(QObject):
    """QObject bridge exposing incident objectives to QML.

    The bridge performs light-weight CRUD operations directly against the
    mission database.  All methods interact with SQLite and update the
    backing list models which are exposed to QML via ``Property``.
    """

    objectivesChanged = Signal()
    detailChanged = Signal()
    toast = Signal(str)

    def __init__(self, mission_db_path: str, current_user_id: int, parent=None):
        super().__init__(parent)
        self._db_path = Path(mission_db_path)
        self._uid = current_user_id
        self._list_model = ObjectiveListModel([])
        self._narrative = SimpleListModel(["ts", "text", "user", "critical"], [])
        self._strategies = SimpleListModel(["text", "user", "ts"], [])
        self._linked = SimpleListModel(["id", "summary", "team", "status"], [])
        self._approvals = SimpleListModel(["ts", "user", "action", "note"], [])
        self._log = SimpleListModel(["type", "ts", "user", "text", "details"], [])
        self.ensure_migration()

    # ------------------------------------------------------------------
    def conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self._db_path))
        con.row_factory = sqlite3.Row
        return con

    def now(self) -> str:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def ensure_migration(self) -> None:
        sql = r"""
        CREATE TABLE IF NOT EXISTS objective_comments (
            id INTEGER PRIMARY KEY,
            objective_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            text TEXT NOT NULL,
            parent_id INTEGER NULL
        );
        CREATE INDEX IF NOT EXISTS idx_objective_comments_obj ON objective_comments(objective_id);
        CREATE TABLE IF NOT EXISTS objective_logs (
            objective_id INTEGER NOT NULL,
            planning_log_id INTEGER NOT NULL,
            PRIMARY KEY (objective_id, planning_log_id)
        );
        CREATE INDEX IF NOT EXISTS idx_incident_objectives_mission ON incident_objectives(mission_id);
        CREATE INDEX IF NOT EXISTS idx_incident_objectives_status ON incident_objectives(status);
        CREATE INDEX IF NOT EXISTS idx_planning_logs_incident ON planning_logs(incident_id);
        """
        with self.conn() as c:
            c.executescript(sql)
            c.commit()

    # ------------------------------------------------------------------
    @Property(QObject, notify=objectivesChanged)
    def objectivesModel(self):  # pragma: no cover - simple property
        return self._list_model

    @Property(QObject, notify=detailChanged)
    def narrativeModel(self):  # pragma: no cover - simple property
        return self._narrative

    @Property(QObject, notify=detailChanged)
    def strategiesModel(self):  # pragma: no cover - simple property
        return self._strategies

    @Property(QObject, notify=detailChanged)
    def linkedTasksModel(self):  # pragma: no cover - simple property
        return self._linked

    @Property(QObject, notify=detailChanged)
    def approvalsModel(self):  # pragma: no cover - simple property
        return self._approvals

    @Property(QObject, notify=detailChanged)
    def logModel(self):  # pragma: no cover - simple property
        return self._log

    # ------------------------------------------------------------------
    @Slot(str, str, str)
    def loadObjectives(self, status_filter: str = "All", priority_filter: str = "All", section_filter: str = "All") -> None:
        q = [
            "SELECT id, printf('%s-%02d', CASE WHEN assigned_section IS 'AIR' THEN 'A' ELSE 'G' END, id) AS code,",
            "CASE WHEN priority IS NULL THEN 'Normal' ELSE priority END AS priority,",
            "status, customer, COALESCE(due_time,'') AS due",
            "FROM incident_objectives",
        ]
        where, params = [], []
        if status_filter != "All":
            where.append("status=?")
            params.append(status_filter)
        if priority_filter != "All":
            where.append("priority=?")
            params.append(priority_filter)
        if section_filter != "All":
            where.append("assigned_section=?")
            params.append(section_filter)
        if where:
            q.append("WHERE " + " AND ".join(where))
        q.append("ORDER BY id DESC")
        sql = "\n".join(q)
        with self.conn() as c:
            rows = [dict(r) for r in c.execute(sql, params)]
        self._list_model.replace(rows)
        self.objectivesChanged.emit()

    @Slot(str, str, int)
    def createObjective(self, description: str, priority: str = "Normal", mission_id: int = 1) -> None:
        ts = self.now()
        with self.conn() as c:
            cur = c.execute(
                "INSERT INTO incident_objectives (mission_id, description, status, priority, created_by, created_at) VALUES (?,?,?,?,?,?)",
                (mission_id, description, "Pending", priority, self._uid, ts),
            )
            oid = cur.lastrowid
            c.execute(
                "INSERT INTO audit_logs (taskid, field_changed, old_value, new_value, changed_by, timestamp) VALUES (?,?,?,?,?,?)",
                (oid, "objective.action", "", "create", self._uid, ts),
            )
            c.commit()
        self.toast.emit("Objective created")
        self.loadObjectives()
        self.loadObjectiveDetail(oid)

    @Slot(int, str)
    def changeStatus(self, oid: int, new_status: str) -> None:
        ts = self.now()
        with self.conn() as c:
            c.execute(
                "UPDATE incident_objectives SET status=?, closed_at=CASE WHEN ? IN ('Completed','Cancelled') THEN ? ELSE closed_at END WHERE id=?",
                (new_status, new_status, ts, oid),
            )
            c.execute(
                "INSERT INTO audit_logs (taskid,field_changed,old_value,new_value,changed_by,timestamp) VALUES (?,?,?,?,?,?)",
                (oid, "objective.action", "", f"status:{new_status}", self._uid, ts),
            )
            c.commit()
        self.toast.emit(f"Status → {new_status}")
        self.loadObjectiveDetail(oid)
        self.loadObjectives()

    # Detail operations --------------------------------------------------
    @Slot(int)
    def loadObjectiveDetail(self, oid: int) -> None:
        """Populate detail models for objective ``oid``."""
        with self.conn() as c:
            narr = [
                dict(r)
                for r in c.execute(
                    """
                    SELECT pl.timestamp AS ts, pl.text, pl.entered_by AS user, 0 AS critical
                    FROM planning_logs pl
                    JOIN objective_logs ol ON pl.id = ol.planning_log_id
                    WHERE ol.objective_id=?
                    ORDER BY pl.timestamp DESC
                    """,
                    (oid,),
                )
            ]
            comments = [
                dict(r)
                for r in c.execute(
                    "SELECT timestamp AS ts, text, user_id AS user, 0 AS critical FROM objective_comments WHERE objective_id=? ORDER BY timestamp",
                    (oid,),
                )
            ]
            log_rows = [
                dict(r)
                for r in c.execute(
                    """
                    SELECT field_changed AS type, timestamp AS ts, changed_by AS user, new_value AS text, old_value AS details
                    FROM audit_logs
                    WHERE taskid=?
                    ORDER BY timestamp
                    """,
                    (oid,),
                )
            ]
        # narrative combines planning_logs and objective_comments
        self._narrative.replace(narr + comments)
        self._strategies.replace([])
        self._linked.replace([])
        self._approvals.replace([])
        self._log.replace(log_rows)
        self.detailChanged.emit()

    @Slot(int, str)
    def addComment(self, oid: int, text: str) -> None:
        ts = self.now()
        with self.conn() as c:
            c.execute(
                "INSERT INTO objective_comments (objective_id, user_id, timestamp, text, parent_id) VALUES (?,?,?,?,NULL)",
                (oid, self._uid, ts, text),
            )
            c.commit()
        self.loadObjectiveDetail(oid)
        self.toast.emit("Comment added")

    @Slot(int, str)
    def addNarrative(self, oid: int, text: str) -> None:
        ts = self.now()
        with self.conn() as c:
            cur = c.execute(
                "INSERT INTO planning_logs (incident_id, text, timestamp, entered_by) VALUES (?,?,?,?)",
                (1, text, ts, self._uid),
            )
            log_id = cur.lastrowid
            c.execute(
                "INSERT INTO objective_logs (objective_id, planning_log_id) VALUES (?,?)",
                (oid, log_id),
            )
            c.commit()
        self.loadObjectiveDetail(oid)
        self.toast.emit("Narrative added")

    # Additional slots such as addStrategy or linking tasks could be added
    # here following the same pattern.
