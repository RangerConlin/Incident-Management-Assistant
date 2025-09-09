from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sqlite3

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot, Property
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6QtAds import CDockWidget

from bridge.incident_bridge import IncidentBridge
from models.database import get_incident_by_number
from utils import incident_context
from utils.app_signals import app_signals
from utils.state import AppState


class _DashboardBridge(QObject):
    """Expose live dashboard data and actions to QML."""

    incidentNameChanged = Signal()
    incidentNumberChanged = Signal()
    incidentTypeChanged = Signal()
    activeUserRoleChanged = Signal()
    opNumberChanged = Signal()
    incidentStatusTextChanged = Signal()
    objectivesChanged = Signal()
    statusSnapshotChanged = Signal()
    recentEventsChanged = Signal()
    alertsHighPriorityChanged = Signal()
    alertsUnackedChanged = Signal()
    bannerTextChanged = Signal()
    opTimelinePrevChanged = Signal()
    opTimelineCurrentChanged = Signal()
    opTimelineNextChanged = Signal()
    localClockChanged = Signal()
    utcClockChanged = Signal()
    timeLeftChanged = Signal()

    def __init__(self) -> None:
        super().__init__()

        self._incidentName = ""
        self._incidentNumber = ""
        self._incidentType = ""
        self._activeUserRole = ""
        self._opNumber = 0
        self._incidentStatusText = ""

        self._localClock = "00:00"
        self._utcClock = "00:00"

        self._objectives: list[dict[str, object]] = []

        self._status = {
            "teams": {"assigned": 0, "available": 0, "oos": 0},
            "personnel": {"total": 0, "checkedIn": 0, "pending": 0},
            "vehicles": {"assigned": 0, "available": 0, "oos": 0},
            "aircraft": {"assigned": 0, "available": 0, "oos": 0},
        }

        self._recentEvents: list[dict[str, object]] = []

        self._alertsHighPriority = 0
        self._alertsUnacked = 0
        self._bannerText = ""

        self._opTimelinePrev = ""
        self._opTimelineCurrent = ""
        self._opTimelineNext = ""

        self._time_left = timedelta(0)
        self._timeLeftHHMMSS = "00:00:00"

        self._ib = IncidentBridge()

        self.refresh()

        app_signals.incidentChanged.connect(lambda *_: self.refresh())
        app_signals.userChanged.connect(lambda *_: self.refresh())
        app_signals.opPeriodChanged.connect(lambda *_: self.refresh())

    @Property(str, notify=incidentNameChanged)
    def incidentName(self) -> str: return self._incidentName

    @Property(str, notify=incidentNumberChanged)
    def incidentNumber(self) -> str: return self._incidentNumber

    @Property(str, notify=incidentTypeChanged)
    def incidentType(self) -> str: return self._incidentType

    @Property(str, notify=activeUserRoleChanged)
    def activeUserRole(self) -> str: return self._activeUserRole

    @Property(int, notify=opNumberChanged)
    def opNumber(self) -> int: return self._opNumber

    @Property(str, notify=incidentStatusTextChanged)
    def incidentStatusText(self) -> str: return self._incidentStatusText

    @Property('QVariantList', notify=objectivesChanged)
    def objectives(self): return self._objectives

    @Property('QVariant', notify=statusSnapshotChanged)
    def statusSnapshot(self): return self._status

    @Property('QVariantList', notify=recentEventsChanged)
    def recentEvents(self): return self._recentEvents

    @Property(int, notify=alertsHighPriorityChanged)
    def alertsHighPriority(self) -> int: return self._alertsHighPriority

    @Property(int, notify=alertsUnackedChanged)
    def alertsUnacked(self) -> int: return self._alertsUnacked

    @Property(str, notify=bannerTextChanged)
    def bannerText(self) -> str: return self._bannerText

    @Property(str, notify=opTimelinePrevChanged)
    def opTimelinePrev(self) -> str: return self._opTimelinePrev

    @Property(str, notify=opTimelineCurrentChanged)
    def opTimelineCurrent(self) -> str: return self._opTimelineCurrent

    @Property(str, notify=opTimelineNextChanged)
    def opTimelineNext(self) -> str: return self._opTimelineNext

    @Property(str, notify=localClockChanged)
    def localClock(self) -> str: return self._localClock

    @Property(str, notify=utcClockChanged)
    def utcClock(self) -> str: return self._utcClock

    @Property(str, notify=timeLeftChanged)
    def timeLeftHHMMSS(self) -> str: return self._timeLeftHHMMSS

    # ------------------------------------------------------------------
    # Data loading helpers
    # ------------------------------------------------------------------

    def _connect_incident_db(self) -> sqlite3.Connection | None:
        try:
            p = incident_context.get_active_incident_db_path()
            con = sqlite3.connect(str(p))
            con.row_factory = sqlite3.Row
            return con
        except Exception:
            return None

    def refresh(self) -> None:
        self._load_incident_details()
        self._load_status_snapshot()
        self._load_objectives()
        self._load_recent_events()
        self._load_op_timeline()
        self._load_comms_summary()

    def _load_incident_details(self) -> None:
        inc_num = AppState.get_active_incident()
        row = get_incident_by_number(inc_num) if inc_num else None
        self._incidentName = row.get("name", "") if row else ""
        self._incidentNumber = row.get("number", "") if row else (inc_num or "")
        self._incidentType = row.get("type", "") if row else ""
        self._incidentStatusText = row.get("status", "") if row else ""
        self._activeUserRole = AppState.get_active_user_role() or ""
        self.incidentNameChanged.emit()
        self.incidentNumberChanged.emit()
        self.incidentTypeChanged.emit()
        self.incidentStatusTextChanged.emit()
        self.activeUserRoleChanged.emit()

    def _load_objectives(self) -> None:
        con = self._connect_incident_db()
        objs: list[dict[str, object]] = []
        if con:
            try:
                cur = con.execute(
                    "SELECT description, priority FROM incident_objectives ORDER BY id LIMIT 5"
                )
                rows = cur.fetchall()
                for idx, r in enumerate(rows, start=1):
                    objs.append(
                        {
                            "index": idx,
                            "priority": (r["priority"] or "").upper(),
                            "text": r["description"] or "",
                        }
                    )
            except Exception:
                pass
            finally:
                con.close()
        self._objectives = objs
        self.objectivesChanged.emit()

    def _load_status_snapshot(self) -> None:
        con = self._connect_incident_db()
        status = {
            "teams": {"assigned": 0, "available": 0, "oos": 0},
            "personnel": {"total": 0, "checkedIn": 0, "pending": 0},
            "vehicles": {"assigned": 0, "available": 0, "oos": 0},
            "aircraft": {"assigned": 0, "available": 0, "oos": 0},
        }
        if con:
            try:
                cur = con.execute("SELECT status, COUNT(*) c FROM teams GROUP BY status")
                rows = {r["status"]: r["c"] for r in cur.fetchall()}
                status["teams"] = {
                    "assigned": rows.get("Assigned", 0),
                    "available": rows.get("Available", 0),
                    "oos": rows.get("OOS", 0) + rows.get("Out of Service", 0),
                }

                cur = con.execute("SELECT COUNT(*) c FROM personnel")
                total = cur.fetchone()["c"]
                status["personnel"] = {
                    "total": total,
                    "checkedIn": total,
                    "pending": 0,
                }

                cur = con.execute("SELECT status_id, COUNT(*) c FROM vehicles GROUP BY status_id")
                vrows = {r["status_id"]: r["c"] for r in cur.fetchall()}
                status["vehicles"] = {
                    "assigned": vrows.get("Assigned", 0),
                    "available": vrows.get("Available", 0),
                    "oos": vrows.get("OOS", 0) + vrows.get("Out of Service", 0),
                }

                cur = con.execute("SELECT status, COUNT(*) c FROM aircraft GROUP BY status")
                arows = {r["status"]: r["c"] for r in cur.fetchall()}
                status["aircraft"] = {
                    "assigned": arows.get("Assigned", 0),
                    "available": arows.get("Available", 0),
                    "oos": arows.get("OOS", 0) + arows.get("Out of Service", 0),
                }
            except Exception:
                pass
            finally:
                con.close()

        self._status = status
        self.statusSnapshotChanged.emit()

    def _load_recent_events(self) -> None:
        rows = []
        try:
            rows = self._ib.listTaskNarrative(0, "", False, "")  # type: ignore[call-arg]
        except Exception:
            pass
        events: list[dict[str, object]] = []
        for r in rows[:6]:
            ts = r.get("timestamp", "")
            time_hhmm = ""
            try:
                time_hhmm = ts[11:16]
            except Exception:
                pass
            events.append(
                {
                    "timeHHMM": time_hhmm,
                    "severity": "CRIT" if r.get("critical") else "INFO",
                    "message": r.get("narrative", ""),
                }
            )
        self._recentEvents = events
        self.recentEventsChanged.emit()

    def _load_op_timeline(self) -> None:
        op_id = AppState.get_active_op_period()
        self._opNumber = 0
        self._opTimelinePrev = ""
        self._opTimelineCurrent = ""
        self._opTimelineNext = ""
        self._time_left = timedelta(0)
        con = self._connect_incident_db()
        if con and op_id is not None:
            try:
                cur = con.execute(
                    "SELECT id, op_number, start_time, end_time FROM operationalperiods ORDER BY id"
                )
                rows = cur.fetchall()
                idx = next((i for i, r in enumerate(rows) if r["id"] == op_id), None)
                if idx is not None:
                    current = rows[idx]
                    self._opNumber = int(current["op_number"])
                    self._opTimelineCurrent = f"OP-{self._opNumber} NOW"
                    if idx > 0:
                        prev = rows[idx - 1]
                        self._opTimelinePrev = f"OP-{prev['op_number']}"
                    if idx + 1 < len(rows):
                        nxt = rows[idx + 1]
                        start = nxt["start_time"]
                        sched = ""
                        if start:
                            try:
                                sched = datetime.fromisoformat(start).strftime("%H:%M")
                            except Exception:
                                sched = str(start)
                        self._opTimelineNext = (
                            f"OP-{nxt['op_number']} (scheduled {sched})" if sched else f"OP-{nxt['op_number']}"
                        )
                    end = current["end_time"]
                    if end:
                        try:
                            end_dt = datetime.fromisoformat(end)
                            self._time_left = max(end_dt - datetime.now(), timedelta(0))
                        except Exception:
                            self._time_left = timedelta(0)
            except Exception:
                pass
            finally:
                con.close()

        self._timeLeftHHMMSS = self._format_td(self._time_left)
        self.opNumberChanged.emit()
        self.opTimelinePrevChanged.emit()
        self.opTimelineCurrentChanged.emit()
        self.opTimelineNextChanged.emit()
        self.timeLeftChanged.emit()

    def _load_comms_summary(self) -> None:
        # TODO: implement real alerts/comms queries when available
        self._alertsHighPriority = 0
        self._alertsUnacked = 0
        self._bannerText = ""
        self.alertsHighPriorityChanged.emit()
        self.alertsUnackedChanged.emit()
        self.bannerTextChanged.emit()

    @staticmethod
    def _format_td(td: timedelta) -> str:
        s = str(td).split(".")[0]
        if len(s) == 7:
            s = "0" + s
        return s

    def update_clocks(self) -> None:
        now = datetime.now()
        self._localClock = now.strftime("%H:%M")
        self._utcClock = datetime.utcnow().strftime("%H:%M")
        self.localClockChanged.emit()
        self.utcClockChanged.emit()

    def update_countdown(self) -> None:
        self._time_left -= timedelta(seconds=1)
        if self._time_left.total_seconds() < 0:
            self._time_left = timedelta(0)
        self._timeLeftHHMMSS = str(self._time_left).split(".")[0]
        if len(self._timeLeftHHMMSS) == 7:
            self._timeLeftHHMMSS = "0" + self._timeLeftHHMMSS
        self.timeLeftChanged.emit()

    @Slot() def openPlanningObjectives(self): print("openPlanningObjectives()")
    @Slot() def openOpsLogs(self): print("openOpsLogs()")
    @Slot() def openCommsCenter(self): print("openCommsCenter()")
    @Slot() def rollOp(self): print("rollOp()")
    @Slot() def openOpScheduler(self): print("openOpScheduler()")
    @Slot() def createObjective(self): print("createObjective()")
    @Slot() def create214Entry(self): print("create214Entry()")
    @Slot() def pauseIncident(self): print("pauseIncident()")
    @Slot() def terminateIncident(self): print("terminateIncident()")
    @Slot() def exportSnapshot(self): print("exportSnapshot()")
    @Slot('QVariant') def selectOp(self, which): print(f"selectOp({which})")
    @Slot(str) def openLogAt(self, timestamp: str): print(f"openLogAt({timestamp})")


class IncidentDashboardPanel(CDockWidget):
    """Dockable Incident Dashboard panel wrapping a QML view."""

    def __init__(self, parent=None) -> None:
        super().__init__("Incident Dashboard — Command", parent)

        self.bridge = _DashboardBridge()
        self.view = QQuickWidget()
        self.view.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self.view.rootContext().setContextProperty("dashboard", self.bridge)

        qml_file = Path(__file__).resolve().parent.parent / "qml" / "IncidentDashboard.qml"
        self.view.setSource(QUrl.fromLocalFile(qml_file.as_posix()))
        self.setWidget(self.view)

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self.bridge.update_clocks)
        self._clock_timer.start(60 * 1000)
        self.bridge.update_clocks()

        self._count_timer = QTimer(self)
        self._count_timer.timeout.connect(self.bridge.update_countdown)
        self._count_timer.start(1000)
        self.bridge.update_countdown()

        self._sc_objective = QShortcut(QKeySequence("Ctrl+O"), self)
        self._sc_objective.activated.connect(self.bridge.createObjective)

        self._sc_logs = QShortcut(QKeySequence("Ctrl+L"), self)
        self._sc_logs.activated.connect(self.bridge.openOpsLogs)

        self._sc_export = QShortcut(QKeySequence("Ctrl+E"), self)
        self._sc_export.activated.connect(self.bridge.exportSnapshot)
