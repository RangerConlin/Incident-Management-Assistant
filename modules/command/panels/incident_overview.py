from __future__ import annotations

"""
Incident Overview panel (PySide6 widgets only).

Strategic, high‑level context about the currently active incident. Designed to
dock within the app's dock manager. Fetches live data from the local HTTP API
in a background thread and tolerates missing endpoints/fields gracefully.
"""

from dataclasses import dataclass
from typing import Any, Optional
import json
import urllib.request
import urllib.error
from datetime import datetime

from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QComboBox,
    QFrame,
    QProgressBar,
    QMessageBox,
)


# ---- Helpers ---------------------------------------------------------------


def _fmt_dt(value: Optional[str]) -> str:
    if not value:
        return "—"
    try:
        # Accept both with and without timezone suffix
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(value)


def _status_color(name: str) -> str:
    n = (name or "").strip().lower()
    # Map to simple background colors (readable with light themes)
    if n == "active":
        return "#2e7d32"  # green
    if n == "standby":
        return "#546e7a"  # blue-gray
    if n == "paused":
        return "#6d4c41"  # brown
    if n == "terminated":
        return "#c62828"  # red
    return "#424242"  # dark gray fallback


def _safe_get(d: dict, key: str, default: str = "—") -> str:
    try:
        v = d.get(key)
        if v in (None, ""):
            return default
        return str(v)
    except Exception:
        return default


def _base_url_from(app_context: Any | None) -> str:
    # Attempt to derive API base from app_context, then env, then default
    # app_context may expose .api_base_url or .settings.get("api.base_url")
    try:
        if app_context is not None:
            url = getattr(app_context, "api_base_url", None)
            if url:
                return str(url).rstrip("/")
            settings = getattr(app_context, "settings", None)
            if settings and isinstance(settings, dict):
                v = settings.get("api.base_url") or settings.get("api_base_url")
                if v:
                    return str(v).rstrip("/")
    except Exception:
        pass
    import os
    env = os.environ.get("IMA_API_BASE_URL") or os.environ.get("API_BASE_URL")
    if env:
        return str(env).rstrip("/")
    # Sensible local default
    return "http://127.0.0.1:8000"


def _http_get(url: str, timeout: float = 5.0) -> tuple[int, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = getattr(resp, "status", 200)
            raw = resp.read()
            try:
                data = json.loads(raw.decode("utf-8")) if raw else {}
            except Exception:
                data = {}
            return code or 200, data
    except urllib.error.HTTPError as e:
        try:
            raw = e.read()
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            data = {}
        return int(e.code), data
    except Exception:
        return 0, {}


# ---- Worker ---------------------------------------------------------------


@dataclass
class OverviewData:
    incident: dict
    periods: list[dict]
    objectives: list[dict]
    critical: dict | None


class FetchWorker(QObject):
    finished = Signal(object)  # OverviewData | None
    failed = Signal(str)

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self._base_url = base_url.rstrip("/")

    @Slot()
    def run(self) -> None:
        # 1) active incident
        code, inc_payload = _http_get(f"{self._base_url}/api/incidents?active=1")
        incident = {}
        if code == 200 and isinstance(inc_payload, dict):
            incident = inc_payload.get("incident") or inc_payload
            if not isinstance(incident, dict):
                incident = {}
        if not incident:
            # No active incident available; still emit with blanks
            self.finished.emit(OverviewData({}, [], [], None))
            return

        incident_id = incident.get("id") or incident.get("number") or incident.get("incident_id")

        # 2) periods
        periods: list[dict] = []
        if incident_id is not None:
            p_code, p_payload = _http_get(f"{self._base_url}/api/incident/{incident_id}/periods")
            if p_code == 200 and isinstance(p_payload, dict):
                raw = p_payload.get("periods") or p_payload.get("data") or []
                if isinstance(raw, list):
                    periods = [p for p in raw if isinstance(p, dict)]

        # 3) objectives
        objectives: list[dict] = []
        if incident_id is not None:
            o_code, o_payload = _http_get(f"{self._base_url}/api/incident/{incident_id}/objectives")
            if o_code == 200 and isinstance(o_payload, dict):
                raw = o_payload.get("objectives") or o_payload.get("data") or []
                if isinstance(raw, list):
                    objectives = [o for o in raw if isinstance(o, dict)]

        # 4) critical (optional)
        critical: dict | None = None
        if incident_id is not None:
            c_code, c_payload = _http_get(f"{self._base_url}/api/incident/{incident_id}/critical")
            if c_code == 200 and isinstance(c_payload, dict):
                critical = {
                    "concerns": c_payload.get("concerns") or [],
                    "pending_decisions": c_payload.get("pending_decisions") or [],
                    "external_coordination": c_payload.get("external_coordination") or [],
                }
            else:
                critical = None

        self.finished.emit(OverviewData(incident, periods, objectives, critical))


# ---- Panel ---------------------------------------------------------------


class IncidentOverviewPanel(QWidget):
    panel_title = "Incident Overview"

    # Navigation hooks
    request_action = Signal(str)
    open_panel = Signal(str)

    def __init__(self, app_context: Any | None = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("IncidentOverviewPanel")
        self._app_context = app_context
        self._base_url = _base_url_from(app_context)
        self._selected_op_id: Any = None

        self._thread: QThread | None = None

        # UI
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # Busy bar
        self._busy = QProgressBar(self)
        self._busy.setRange(0, 0)
        self._busy.setTextVisible(False)
        self._busy.hide()
        root.addWidget(self._busy)

        # Header box
        header = QGroupBox("Incident")
        h_layout = QVBoxLayout(header)
        self._title_label = QLabel("—")
        font = self._title_label.font()
        font.setPointSize(font.pointSize() + 4)
        font.setBold(True)
        self._title_label.setFont(font)

        title_row = QHBoxLayout()
        title_row.addWidget(self._title_label, 1)
        self._status_badge = QLabel("—")
        self._status_badge.setAlignment(Qt.AlignCenter)
        self._status_badge.setStyleSheet("border-radius: 10px; padding: 4px 8px; color: white; background: #424242;")
        title_row.addWidget(self._status_badge, 0)
        h_layout.addLayout(title_row)

        self._meta_label = QLabel("—")
        self._meta_label.setWordWrap(True)
        h_layout.addWidget(self._meta_label)

        actions_row = QHBoxLayout()
        actions_row.addStretch(1)
        self._btn_manage_ops = QPushButton("Manage Operational Periods")
        self._btn_view_objectives = QPushButton("View All Objectives")
        self._btn_refresh = QPushButton("Refresh")
        actions_row.addWidget(self._btn_manage_ops)
        actions_row.addWidget(self._btn_view_objectives)
        actions_row.addWidget(self._btn_refresh)
        h_layout.addLayout(actions_row)
        root.addWidget(header)

        # Operational Periods
        op_box = QGroupBox("Operational Periods")
        op_layout = QVBoxLayout(op_box)
        op_top = QHBoxLayout()
        self._op_selector = QComboBox()
        self._op_selector.currentIndexChanged.connect(self._update_op_details)
        op_top.addWidget(QLabel("Select OP:"))
        op_top.addWidget(self._op_selector, 1)
        op_layout.addLayout(op_top)

        self._op_focus = QLabel("—")
        self._op_focus.setWordWrap(True)
        op_layout.addWidget(QLabel("Focus / Goal:"))
        op_layout.addWidget(self._op_focus)
        root.addWidget(op_box)

        # Primary Objectives
        obj_box = QGroupBox("Primary Objectives")
        obj_layout = QVBoxLayout(obj_box)
        self._objectives_list = QListWidget()
        self._objectives_list.setCursor(QCursor(Qt.PointingHandCursor))
        self._objectives_list.itemActivated.connect(lambda _i: self.open_panel.emit("planning.objectives"))
        self._objectives_list.viewport().installEventFilter(self)  # to catch block clicks
        obj_layout.addWidget(self._objectives_list)

        # Critical Information
        crit_box = QGroupBox("Critical Information")
        crit_layout = QHBoxLayout(crit_box)

        self._crit_concerns = self._make_bullet_list_group("Priority Concerns")
        self._crit_decisions = self._make_bullet_list_group("Decisions Pending")
        self._crit_external = self._make_bullet_list_group("External Coordination")

        crit_layout.addWidget(self._crit_concerns)
        crit_layout.addWidget(self._crit_decisions)
        crit_layout.addWidget(self._crit_external)

        # Row: Objectives + Critical side by side
        row = QHBoxLayout()
        row.addWidget(obj_box, 1)
        row.addWidget(crit_box, 2)
        root.addLayout(row)

        # Map placeholder
        map_frame = QFrame()
        map_frame.setFrameShape(QFrame.StyledPanel)
        map_frame.setFixedHeight(180)
        map_layout = QVBoxLayout(map_frame)
        map_label = QLabel("Map / Diagram (future)")
        map_label.setAlignment(Qt.AlignCenter)
        map_layout.addWidget(map_label)
        root.addWidget(map_frame)

        # Wire actions
        self._btn_refresh.clicked.connect(self.refresh)
        self._btn_manage_ops.clicked.connect(lambda: self.open_panel.emit("planning.operational_periods"))
        self._btn_view_objectives.clicked.connect(lambda: self.open_panel.emit("planning.objectives"))

        # Initial state
        self.refresh()

    # ---- Event handling -------------------------------------------------
    def eventFilter(self, obj, event):  # noqa: N802 - Qt override
        # Clicking empty space in objectives block opens objectives
        from PySide6.QtCore import QEvent
        if obj is self._objectives_list.viewport() and event.type() == QEvent.MouseButtonRelease:
            self.open_panel.emit("planning.objectives")
            return True
        return super().eventFilter(obj, event)

    # ---- UI builders ----------------------------------------------------
    def _make_bullet_list_group(self, title: str) -> QGroupBox:
        box = QGroupBox(title)
        v = QVBoxLayout(box)
        lst = QListWidget()
        v.addWidget(lst)
        # Store reference on the group box for easy access
        box._list_widget = lst  # type: ignore[attr-defined]
        return box

    # ---- Data refresh ---------------------------------------------------
    @Slot()
    def refresh(self) -> None:
        if self._thread and self._thread.isRunning():
            return
        self._busy.show()
        worker = FetchWorker(self._base_url)
        thread = QThread(self)
        self._thread = thread
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._handle_data)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._busy.hide)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    @Slot(object)
    def _handle_data(self, payload: object) -> None:
        if not isinstance(payload, OverviewData):
            QMessageBox.warning(self, "Incident Overview", "Unable to load overview data.")
            return
        self._apply_incident(payload.incident)
        self._apply_periods(payload.periods)
        self._apply_objectives(payload.objectives)
        self._apply_critical(payload.critical)

    # ---- Apply sections -------------------------------------------------
    def _apply_incident(self, incident: dict) -> None:
        name = _safe_get(incident, "name")
        number = _safe_get(incident, "number")
        self._title_label.setText(f"{name}  (#{number})")

        status = _safe_get(incident, "status")
        self._status_badge.setText(status)
        self._status_badge.setStyleSheet(
            f"border-radius: 10px; padding: 4px 8px; color: white; background: {_status_color(status)};"
        )

        ic_name = _safe_get(incident, "commander_name")
        ic_agency = _safe_get(incident, "commander_agency")
        start_time = _fmt_dt(incident.get("start_time_iso") or incident.get("start_time"))
        itype = _safe_get(incident, "type")
        self._meta_label.setText(f"IC: {ic_name} ({ic_agency})  •  Start: {start_time}  •  Type: {itype}")

        # Stash for later calls
        self._incident_id = incident.get("id") or incident.get("number") or incident.get("incident_id")

    def _apply_periods(self, periods: list[dict]) -> None:
        # Preserve selection if possible
        prev_id = self._selected_op_id
        self._op_selector.blockSignals(True)
        self._op_selector.clear()
        # Build focus mapping by id for quick lookup
        focus_map: dict[Any, str] = {}
        if not periods:
            self._op_selector.addItem("— No periods —", None)
            self._op_focus.setText("—")
            self._op_selector.blockSignals(False)
            return

        # Prefer ordering by op_number, falling back to start_time
        def _sort_key(p: dict):
            try:
                return int(p.get("op_number") or 0)
            except Exception:
                return 0

        periods_sorted = sorted(periods, key=_sort_key)
        for p in periods_sorted:
            opn = p.get("op_number") or p.get("number") or "?"
            start = _fmt_dt(p.get("start_time") or p.get("start") or p.get("start_time_iso"))
            end = _fmt_dt(p.get("end_time") or p.get("end") or p.get("end_time_iso"))
            label = f"OP {opn}: {start} → {end}"
            pid = p.get("id") or p.get("op_id") or opn
            self._op_selector.addItem(label, pid)
            focus_text = p.get("focus") or p.get("goal") or p.get("summary") or "—"
            focus_map[pid] = str(focus_text) if focus_text else "—"

        # Save focus map
        self._period_focus_by_id = focus_map  # type: ignore[attr-defined]

        # Restore selection by id if available; otherwise select last
        index = -1
        if prev_id is not None:
            for i in range(self._op_selector.count()):
                if self._op_selector.itemData(i) == prev_id:
                    index = i
                    break
        if index == -1:
            index = self._op_selector.count() - 1
        self._op_selector.setCurrentIndex(max(0, index))
        self._op_selector.blockSignals(False)
        self._update_op_details()

    @Slot()
    def _update_op_details(self) -> None:
        idx = self._op_selector.currentIndex()
        if idx < 0:
            self._op_focus.setText("—")
            self._selected_op_id = None
            return
        self._selected_op_id = self._op_selector.itemData(idx)
        # focus text was not stored; refresh text from accessible label content in combo text if no data
        # Since worker doesn't pass full period map here, we keep it simple: display focus if cached elsewhere
        # The focus is not readily available; show placeholder retained on apply_periods if necessary.
        # To provide focus, we embed it in the combo's user data when available in apply_periods.
        # For now, set via tooltip if present in item text.
        text = self._op_selector.itemText(idx)
        focus = getattr(self, "_period_focus_by_id", {}).get(self._selected_op_id, "—") if hasattr(self, "_period_focus_by_id") else "—"
        if not focus or focus == "—":
            # No stored mapping; leave placeholder
            pass
        self._op_focus.setText(focus or "—")

    def _apply_objectives(self, objectives: list[dict]) -> None:
        self._objectives_list.clear()
        if not objectives:
            self._objectives_list.addItem("— No objectives recorded —")
            return
        # Sort by priority if numeric; otherwise keep order
        try:
            objectives = sorted(objectives, key=lambda o: int(o.get("priority") or 999999))
        except Exception:
            pass
        top = objectives[:5]
        for obj in top:
            pri = obj.get("priority")
            text = obj.get("text") or obj.get("description") or obj.get("objective") or ""
            if pri is None:
                label = f"{text}"
            else:
                label = f"[{pri}] {text}"
            item = QListWidgetItem(label or "—")
            self._objectives_list.addItem(item)

    def _apply_critical(self, critical: Optional[dict]) -> None:
        def _fill(box: QGroupBox, items: list[str] | None) -> None:
            lst: QListWidget = getattr(box, "_list_widget")  # type: ignore[assignment]
            lst.clear()
            if not items:
                lst.addItem("— None recorded —")
                return
            for s in items:
                lst.addItem(str(s))

        if not critical:
            for b in (self._crit_concerns, self._crit_decisions, self._crit_external):
                _fill(b, [])
            return
        _fill(self._crit_concerns, critical.get("concerns") or [])
        _fill(self._crit_decisions, critical.get("pending_decisions") or [])
        _fill(self._crit_external, critical.get("external_coordination") or [])


# ---- Factory --------------------------------------------------------------


def create_command_incident_overview_panel(dock_manager: Any, app_context: Any) -> QWidget:
    """Factory to create the dock‑friendly Incident Overview widget.

    The returned widget emits `open_panel` routes such as
    "planning.operational_periods" and "planning.objectives". This factory
    wires those to the app's router when available.
    """
    panel = IncidentOverviewPanel(app_context=app_context)

    def _route_to(route: str) -> None:
        # Try to resolve a router from dock_manager or its window
        route_map = {
            "planning.operational_periods": "planning.op_manager",
            "planning.objectives": "command.objectives",
        }
        target_route = route_map.get(route, route)
        target = None
        try:
            target = getattr(dock_manager, "open_module", None)
            if callable(target):
                target(target_route)
                return
        except Exception:
            target = None
        # Fallback to main window
        try:
            win = dock_manager.parent() if hasattr(dock_manager, "parent") else None
            opener = getattr(win, "open_module", None) if win else None
            if callable(opener):
                opener(target_route)
                return
        except Exception:
            pass
        # As a last resort, emit a no-op warning dialog to avoid silent failure
        try:
            QMessageBox.information(panel, "Navigation", f"Requested route: {target_route}")
        except Exception:
            pass

    panel.open_panel.connect(_route_to)
    # request_action reserved for future command hooks
    return panel


__all__ = [
    "IncidentOverviewPanel",
    "create_command_incident_overview_panel",
]
