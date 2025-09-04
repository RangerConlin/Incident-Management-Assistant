# ===== Part 1: Imports & Logging ============================================
import os
import sys
import logging
from typing import Callable

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QLabel,
    QWidget,
    QVBoxLayout,
    QMessageBox,
    QDialog,
    QListWidget,
    QPushButton,
    QHBoxLayout,
    QInputDialog,
)
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtCore import Qt, QUrl, QSettings, QTimer
from PySide6.QtQuick import QQuickView
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtQuick import QQuickWindow
from PySide6QtAds import (
    CDockManager,
    CDockWidget,
    LeftDockWidgetArea,
    RightDockWidgetArea,
    TopDockWidgetArea,
    BottomDockWidgetArea,
    CenterDockWidgetArea,
)
QQuickStyle.setStyle("Fusion")


# Force a known-good default dock layout on startup (ignores saved layouts)
FORCE_DEFAULT_LAYOUT = True


# (QML utilities kept, though handlers now follow panel-factory pattern)
from models.qmlwindow import QmlWindow, new_incident_form, open_incident_list
from utils.state import AppState
from models.database import get_incident_by_number
from bridge.settings_bridge import QmlSettingsBridge
from utils.settingsmanager import SettingsManager
from bridge.catalog_bridge import CatalogBridge
from bridge.incident_bridge import IncidentBridge
from models.sqlite_table_model import SqliteTableModel
import sqlite3
# 'os' imported earlier for env setup
from utils.styles import set_theme, apply_app_palette, THEME_NAME
from utils.audit import fetch_last_audit_rows, write_audit
from utils.session import end_session
from utils.constants import TEAM_STATUSES

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
)



# ===== Part 2: Main Window & Physical Menus (visible UI only) ===============
class MainWindow(QMainWindow):
    """
    Menu-first structure. Every visible menu item has a corresponding handler method,
    and ALL handlers follow the same pattern:
      - import module
      - incident_id = getattr(self, "current_incident_id", None)
      - panel = module.get_*_panel(incident_id)
      - self._open_dock_widget(panel, title="...")
    Placeholders are fine if a real module/factory doesn't exist yet.
    """
    def __init__(self, settings_manager: SettingsManager | None = None,
                 settings_bridge: QmlSettingsBridge | None = None):
        super().__init__()
        self.setStyleSheet("background-color: #f5f5f5;")

        if settings_manager is None:
            settings_manager = SettingsManager()
        if settings_bridge is None:
            settings_bridge = QmlSettingsBridge(settings_manager)
        self.settings_manager = settings_manager
        self.settings_bridge = settings_bridge

        # Prepare a Mission Status label (will live inside a dock, not fixed)
        self.active_incident_label = QLabel()
        self.update_active_incident_label()

        # Title includes active incident (if any)
        active_number = AppState.get_active_incident()
        user_id = AppState.get_active_user_id()
        user_role = AppState.get_active_user_role()
        suffix = f" — User: {user_id or ''} ({user_role or ''})" if (user_id or user_role) else ""
        if active_number:
            incident = get_incident_by_number(active_number)
            if incident:
                title = f"SARApp - {incident['number']} | {incident['name']}{suffix}"
            else:
                title = f"SARApp - No Incident Loaded{suffix}"
        else:
            title = f"SARApp - No Incident Loaded{suffix}"
        self.setWindowTitle(title)
        self.resize(1280, 800)

        # Central widget with persistent header and ADS dock manager
        central = QWidget()
        central_layout = QVBoxLayout(central)
        try:
            central_layout.setContentsMargins(0, 0, 0, 0)
            central_layout.setSpacing(0)
        except Exception:
            pass
        # Only a dock container in the central area; status goes to a dock
        self._dock_container = QWidget()
        central_layout.addWidget(self._dock_container)
        try:
            cont_layout = QVBoxLayout(self._dock_container)
            cont_layout.setContentsMargins(0, 0, 0, 0)
            cont_layout.setSpacing(0)
        except Exception:
            pass
        self.setCentralWidget(central)

        self.dock_manager = CDockManager(self._dock_container)
        # If CDockManager is a QWidget, add to container layout to fill area
        try:
            cont_layout.addWidget(self.dock_manager)  # type: ignore[name-defined]
        except Exception:
            pass

        # Load persisted perspectives if available (unless forced default)
        self._perspective_file = os.path.join("settings", "ads_perspectives.ini")
        opened_default = False
        if FORCE_DEFAULT_LAYOUT:
            # Clear any saved layout and seed defaults immediately
            try:
                settings_obj = QSettings(self._perspective_file, QSettings.IniFormat)
                settings_obj.clear()
            except Exception:
                pass
            self._reset_layout()
            opened_default = True
        else:
            try:
                settings_obj = QSettings(self._perspective_file, QSettings.IniFormat)
                self.dock_manager.loadPerspectives(settings_obj)
                names = []
                try:
                    names = list(self.dock_manager.perspectiveNames())
                except Exception:
                    names = []
                if "default" in names:
                    try:
                        rv = self.dock_manager.openPerspective("default")
                        opened_default = bool(rv) if rv is not None else True
                    except Exception:
                        opened_default = False
            except Exception as e:
                logger.warning("Failed to load ADS perspectives: %s", e)

        # Build the physical menu bar (visible UI)
        self.init_module_menus()

        # If no saved layout was opened, create some default docks to play with
        # Seed defaults if not forced and no perspective opened or nothing is docked
        if not FORCE_DEFAULT_LAYOUT:
            try:
                names = []
                try:
                    names = list(self.dock_manager.perspectiveNames())
                except Exception:
                    names = []
                has_any_docks = bool(self.findChildren(CDockWidget))
                if (not opened_default) or (not has_any_docks):
                    self._create_default_docks()
            except Exception:
                self._create_default_docks()

    # ----- Part 2.A: Physical Menu Builder ----------------------------------
    def _add_action(self, menu: QMenu, text: str, keyseq: str | None, module_key: str):
        """Create a QAction, attach module_key, connect to router, and add to menu."""
        act = QAction(text, self)
        if keyseq:
            act.setShortcut(QKeySequence(keyseq))
        act.setData({"module_key": module_key})
        act.triggered.connect(lambda: self.open_module(module_key))
        menu.addAction(act)
        return act

    def init_module_menus(self):
        """Build the entire menu tree in one place; handlers live below."""
        mb = self.menuBar()

        # ----- Menu -----
        m_menu = mb.addMenu("Menu")
        self._add_action(m_menu, "New Incident", "Ctrl+N", "menu.new_incident")
        self._add_action(m_menu, "Open Incident", "Ctrl+O", "menu.open_incident")
        self._add_action(m_menu, "Save Incident", "Ctrl+S", "menu.save_incident")
        self._add_action(m_menu, "Settings", None, "menu.settings")
        m_menu.addSeparator()
        self._add_action(m_menu, "Exit", "Ctrl+Q", "menu.exit")

        # ----- Edit -----
        m_edit = mb.addMenu("Edit")
        self._add_action(m_edit, "EMS Agencies", None, "edit.ems")
        self._add_action(m_edit, "Hospitals", None, "edit.hospitals")
        self._add_action(m_edit, "Canned Communication Entries", None, "edit.canned_comm_entries")
        self._add_action(m_edit, "Personnel", None, "edit.personnel")
        self._add_action(m_edit, "Objectives", None, "edit.objectives")
        self._add_action(m_edit, "Task Types", None, "edit.task_types")
        self._add_action(m_edit, "Team Types", None, "edit.team_types")
        self._add_action(m_edit, "Vehicles", None, "edit.vehicles")
        self._add_action(m_edit, "Aircraft", None, "edit.aircraft")
        self._add_action(m_edit, "Equipment", None, "edit.equipment")
        self._add_action(m_edit, "Communications Resources (ICS-217)", None, "communications.217")
        self._add_action(m_edit, "Safety Analysis Templates", None, "edit.safety_templates")

        # ----- View -----
        m_view = mb.addMenu("View")
        theme_menu = m_view.addMenu("Theme")
        act_light = QAction("Light", self)
        act_light.setCheckable(True)
        act_dark = QAction("Dark", self)
        act_dark.setCheckable(True)
        if THEME_NAME == "light":
            act_light.setChecked(True)
        else:
            act_dark.setChecked(True)
        act_light.triggered.connect(lambda: (set_theme("light"), apply_app_palette(QApplication.instance())))
        act_dark.triggered.connect(lambda: (set_theme("dark"), apply_app_palette(QApplication.instance())))
        theme_menu.addAction(act_light)
        theme_menu.addAction(act_dark)

        # ----- Command -----
        m_cmd = mb.addMenu("Command")
        self._add_action(m_cmd, "Command Unit Log ICS-214", None, "command.unit_log")
        m_cmd.addSeparator()
        self._add_action(m_cmd, "Incident Overview", None, "command.incident_overview")
        self._add_action(m_cmd, "Incident Action Plan Builder", None, "command.iap")
        self._add_action(m_cmd, "Incident Objectives (ICS 202)", None, "command.objectives")
        self._add_action(m_cmd, "Command Staff Organization (ICS 203)", None, "command.staff_org")
        self._add_action(m_cmd, "Situation Report (ICS 209)", None, "command.sitrep")

        # ----- Planning -----
        m_plan = mb.addMenu("Planning")
        self._add_action(m_plan, "Planning Unit Log ICS-214", None, "planning.unit_log")
        m_plan.addSeparator()
        self._add_action(m_plan, "Planning Dashboard", "Ctrl+Alt+D", "planning.dashboard")
        self._add_action(m_plan, "Pending Approvals", None, "planning.approvals")
        self._add_action(m_plan, "Planning Forecast", None, "planning.forecast")
        self._add_action(m_plan, "Operational Period Manager", None, "planning.op_manager")
        self._add_action(m_plan, "Task Metrics Dashboard", None, "planning.taskmetrics")
        self._add_action(m_plan, "Strategic Objective Tracker", None, "planning.strategic_objectives")
        self._add_action(m_plan, "Situation Report", None, "planning.sitrep")

        # ----- Operations -----
        m_ops = mb.addMenu("Operations")
        self._add_action(m_ops, "Operations Unit Log ICS-214", None, "operations.unit_log")
        m_ops.addSeparator()
        self._add_action(m_ops, "Assignments Dashboard", "Ctrl+1", "operations.dashboard")
        self._add_action(m_ops, "Team Assignments", None, "operations.team_assignments")
        self._add_action(m_ops, "Team Status Board", None, "operations.team_status")
        self._add_action(m_ops, "Task Board", None, "operations.task_board")
        self._add_action(m_ops, "Narrative", None, "operations.narrative")

        # ----- Logistics -----
        m_log = mb.addMenu("Logistics")
        self._add_action(m_log, "Logistics Unit Log ICS-214", None, "logistics.unit_log")
        m_log.addSeparator()
        self._add_action(m_log, "Logistics Dashboard", "Ctrl+L", "logistics.dashboard")
        self._add_action(m_log, "Check-In ICS-211", None, "logistics.211")
        self._add_action(m_log, "Resource Requests", "Ctrl+Shift+R", "logistics.requests")
        self._add_action(m_log, "Equipment Inventory", None, "logistics.equipment")
        self._add_action(m_log, "Resource Requests (ICS-213RR)", None, "logistics.213rr")

        # ----- Communications -----
        m_comms = mb.addMenu("Communications")
        self._add_action(m_comms, "Communications Unit Log ICS-214", None, "comms.unit_log")
        m_comms.addSeparator()
        self._add_action(m_comms, "Messaging", None, "comms.chat")
        self._add_action(m_comms, "ICS 213 Messages", None, "comms.213")
        self._add_action(m_comms, "Communications Plan ICS-205", None, "comms.205")

        # ----- Intel -----
        m_intel = mb.addMenu("Intel")
        self._add_action(m_intel, "Intel Unit Log ICS-214", None, "intel.unit_log")
        m_intel.addSeparator()
        self._add_action(m_intel, "Intel Dashboard", None, "intel.dashboard")
        self._add_action(m_intel, "Clue Log", None, "intel.clue_log")
        self._add_action(m_intel, "Add Clue", None, "intel.add_clue")

        # ----- Medical & Safety -----
        m_med = mb.addMenu("Medical && Safety")
        self._add_action(m_med, "Medical Unit Log ICS-214", None, "medical.unit_log")
        self._add_action(m_med, "Safety Unit Log ICS-214", None, "safety.unit_log")
        m_med.addSeparator()
        self._add_action(m_med, "Medical Plan ICS 206", None, "medical.206")
        self._add_action(m_med, "Safety Message ICS-208", None, "safety.208")
        self._add_action(m_med, "Incident Safety Analysis ICS-215A", None, "safety.215A")
        self._add_action(m_med, "CAP ORM", None, "safety.caporm")

        # ----- Liaison -----
        m_lia = mb.addMenu("Liaison")
        self._add_action(m_lia, "Liaison Unit Log ICS-214", None, "liaison.unit_log")
        m_lia.addSeparator()
        self._add_action(m_lia, "Agency Directory", None, "liaison.agencies")
        self._add_action(m_lia, "Customer Requests", None, "liaison.requests")

        # ----- Public Information -----
        m_pub = mb.addMenu("Public Information")
        self._add_action(m_pub, "Public Information Unit Log ICS-214", None, "public.unit_log")
        m_pub.addSeparator()
        self._add_action(m_pub, "Media Releases", None, "public.media_releases")
        self._add_action(m_pub, "Public Inquiries", None, "public.inquiries")

        # ----- Finance/Admin -----
        m_fin = mb.addMenu("Finance/Admin")
        self._add_action(m_fin, "Finance Unit Log ICS-214", None, "finance.unit_log")
        m_fin.addSeparator()
        self._add_action(m_fin, "Time Tracking", None, "finance.time")
        self._add_action(m_fin, "Expenses && Procurement", None, "finance.procurement")
        self._add_action(m_fin, "Cost Summary", None, "finance.summary")

        # ----- Toolkits -----
        m_tool = mb.addMenu("Toolkits")
        sar_menu = m_tool.addMenu("SAR Toolkit")
        self._add_action(sar_menu, "Missing Person Toolkit", None, "toolkit.sar.missing_person")
        self._add_action(sar_menu, "POD Calculator", None, "toolkit.sar.pod")

        dis_menu = m_tool.addMenu("Disaster Toolkit")
        self._add_action(dis_menu, "Damage Assessment", None, "toolkit.disaster.damage")
        self._add_action(dis_menu, "Urban Interview Log", None, "toolkit.disaster.urban_interview")
        self._add_action(dis_menu, "Damage Photos", None, "toolkit.disaster.photos")

        plan_menu = m_tool.addMenu("Planned Event Toolkit")
        self._add_action(plan_menu, "External Messaging", None, "planned.promotions")
        self._add_action(plan_menu, "Vendors && Permits", None, "planned.vendors")
        self._add_action(plan_menu, "Public Safety", None, "planned.safety")
        self._add_action(plan_menu, "Tasking && Assignments", None, "planned.tasking")
        self._add_action(plan_menu, "Health && Sanitation", None, "planned.health_sanitation")

        init_menu = m_tool.addMenu("Initial Response")
        self._add_action(init_menu, "Hasty Tools", None, "toolkit.initial.hasty")
        self._add_action(init_menu, "Reflex Taskings", None, "toolkit.initial.reflex")

        # ----- Forms & Library -----
        m_forms = self.menuBar().addMenu("Resources")
        self._add_action(m_forms, "Form Library", None, "forms")
        self._add_action(m_forms, "Reference Library", None, "library")
        m_forms.addSeparator()
        self._add_action(m_forms, "User Guide", None, "help.user_guide")

        # ----- Help -----
        m_help = self.menuBar().addMenu("Help")
        self._add_action(m_help, "About", None, "help.about")
        self._add_action(m_help, "User Guide", None, "help.user_guide")

        # ----- Window -----
        m_window = self.menuBar().addMenu("Window")
        self._add_action(m_window, "Home Dashboard", "Ctrl+H", "window.home_dashboard")

        # Widgets submenu: list all registry widgets for ad-hoc placement
        try:
            from ui.widgets import registry as W
        except Exception:
            W = None  # type: ignore
        m_widgets = m_window.addMenu("Widgets")
        if W and hasattr(W, "REGISTRY"):
            for wid, spec in sorted(W.REGISTRY.items(), key=lambda kv: kv[1].title.lower()):
                if wid == "quickEntryCLI":
                    # CLI is embedded inside Quick Entry per spec; skip standalone menu item
                    continue
                self._add_action(m_widgets, spec.title, None, f"widgets.{wid}")

        # Templates manager for saving/loading/deleting ADS perspectives
        act_templates = QAction("Display Templates...", self)
        act_templates.triggered.connect(self.open_display_templates_dialog)
        m_window.addAction(act_templates)

        # Lock/Unlock docking interactions
        self.act_lock_docking = QAction("Lock Docking", self)
        self.act_lock_docking.setCheckable(True)
        self.act_lock_docking.setChecked(False)
        self.act_lock_docking.toggled.connect(self.toggle_dock_lock)
        m_window.addAction(self.act_lock_docking)

        m_window.addSeparator()

        # Existing: open a new floating workspace window
        act_new_ws = QAction("New Workspace Window", self)
        act_new_ws.triggered.connect(self.open_new_workspace_window)
        m_window.addAction(act_new_ws)

        # ----- Debug -----
        self.menuDebug = self.menuBar().addMenu("Debug")
        act = QAction("Print Active Incident", self)
        act.triggered.connect(lambda: print(f"[debug] MainWindow current_incident_id={getattr(self,'current_incident_id',None)}; AppState={AppState.get_active_incident()}"))
        self.menuDebug.addAction(act)

        # Quick way to add sample docks to play with ADS
        act_defaults = QAction("Open Default Docks", self)
        act_defaults.triggered.connect(self._create_default_docks)
        self.menuDebug.addAction(act_defaults)

        act_reset = QAction("Reset Layout (Default)", self)
        act_reset.triggered.connect(self._reset_layout)
        self.menuDebug.addAction(act_reset)

        # Quick QML-openers for troubleshooting (bypass QWidget panels)
        act_team_qml = QAction("Open Team Status (QML)", self)
        act_team_qml.triggered.connect(lambda: self._open_team_status_qml_debug())
        self.menuDebug.addAction(act_team_qml)
        act_task_qml = QAction("Open Task Status (QML)", self)
        act_task_qml.triggered.connect(lambda: self._open_task_status_qml_debug())
        self.menuDebug.addAction(act_task_qml)

        act_audit = QAction("Audit Console", self)
        def _show_audit():
            try:
                rows = fetch_last_audit_rows()
                for row in rows:
                    print(dict(row))
            except Exception as e:
                print(f"[debug] failed to fetch audit logs: {e}")
        act_audit.triggered.connect(_show_audit)
        self.menuDebug.addAction(act_audit)

        # Debug: Open Team Detail by ID
        act_team_detail = QAction("Open Team Detail (Team ID…)", self)
        def _open_team_detail_prompt():
            try:
                from PySide6.QtWidgets import QInputDialog
                team_id, ok = QInputDialog.getInt(self, "Open Team Detail", "Team ID:", 1, 1, 10_000_000, 1)
                if ok:
                    from modules.operations.teams.windows import open_team_detail_window
                    open_team_detail_window(int(team_id))
            except Exception as e:
                print(f"[debug] failed to open Team Detail: {e}")
        act_team_detail.triggered.connect(_open_team_detail_prompt)
        self.menuDebug.addAction(act_team_detail)

        self._gate_menus_by_availability({})
        # you can toggle feature availability here, e.g.: {"planned.promotions": False}

    def _gate_menus_by_availability(self, enabled_map: dict[str, bool]):
        """Grey-out actions whose module keys are disabled in enabled_map."""
        for menu in self.menuBar().findChildren(QMenu):
            for act in menu.actions():
                data = act.data()
                if isinstance(data, dict) and "module_key" in data:
                    key = data["module_key"]
                    if key in enabled_map:
                        act.setEnabled(bool(enabled_map[key]))

    # ===== Part 3: Central Router (module_key -> handler) ====================
    def open_module(self, key: str):
        """Central router: call explicit handler for every menu item (panel pattern)."""
        # Dynamic widget openers
        if key.startswith("widgets."):
            widget_id = key.split(".", 1)[1]
            return self.open_widget_with_id(widget_id)
        handlers: dict[str, Callable[[], None]] = {
            # ----- Menu -----
            "menu.new_incident": self.open_menu_new_incident,
            "menu.open_incident": self.open_menu_open_incident,
            "menu.save_incident": self.open_menu_save_incident,
            "menu.settings": self.open_menu_settings,
            "menu.exit": self.open_menu_exit,  # special-case: still exits

            # ----- Edit -----
            "edit.ems": self.open_edit_ems,
            "edit.hospitals": self.open_edit_hospitals,
            "edit.canned_comm_entries": self.open_edit_canned_comm_entries,
            "edit.personnel": self.open_edit_personnel,
            "edit.objectives": self.open_edit_objectives,
            "edit.task_types": self.open_edit_task_types,
            "edit.team_types": self.open_edit_team_types,
            "edit.vehicles": self.open_edit_vehicles,
            "edit.aircraft": self.open_edit_aircraft,
            "edit.equipment": self.open_edit_equipment,
            "communications.217": self.open_edit_comms_resources,
            "edit.safety_templates": self.open_edit_safety_templates,

            # ----- Command -----
            "command.unit_log": self.open_command_unit_log,
            "command.incident_overview": self.open_command_incident_overview,
            "command.iap": self.open_command_iap,
            "command.objectives": self.open_command_objectives,
            "command.staff_org": self.open_command_staff_org,
            "command.sitrep": self.open_command_sitrep,

            # ----- Planning -----
            "planning.unit_log": self.open_planning_unit_log,
            "planning.dashboard": self.open_planning_dashboard,
            "planning.approvals": self.open_planning_approvals,
            "planning.forecast": self.open_planning_forecast,
            "planning.op_manager": self.open_planning_op_manager,
            "planning.taskmetrics": self.open_planning_taskmetrics,
            "planning.strategic_objectives": self.open_planning_strategic_objectives,
            "planning.sitrep": self.open_planning_sitrep,

            # ----- Operations -----
            "operations.unit_log": self.open_operations_unit_log,
            "operations.dashboard": self.open_operations_dashboard,
            "operations.team_assignments": self.open_operations_team_assignments,
            "operations.team_status": self.open_operations_team_status,
            "operations.task_board": self.open_operations_task_board,
            "operations.narrative": self.open_operations_narrative,

            # ----- Logistics -----
            "logistics.unit_log": self.open_logistics_unit_log,
            "logistics.dashboard": self.open_logistics_dashboard,
            "logistics.211": self.open_logistics_211,
            "logistics.requests": self.open_logistics_requests,
            "logistics.equipment": self.open_logistics_equipment,
            "logistics.213rr": self.open_logistics_213rr,

            # ----- Communications -----
            "comms.unit_log": self.open_comms_unit_log,
            "comms.chat": self.open_comms_chat,
            "comms.213": self.open_comms_213,
            "comms.205": self.open_comms_205,

            # ----- Intel -----
            "intel.unit_log": self.open_intel_unit_log,
            "intel.dashboard": self.open_intel_dashboard,
            "intel.clue_log": self.open_intel_clue_log,
            "intel.add_clue": self.open_intel_add_clue,

            # ----- Medical & Safety -----
            "medical.unit_log": self.open_medical_unit_log,
            "safety.unit_log": self.open_safety_unit_log,
            "medical.206": self.open_medical_206,
            "safety.208": self.open_safety_208,
            "safety.215A": self.open_safety_215A,
            "safety.caporm": self.open_safety_caporm,

            # ----- Liaison -----
            "liaison.unit_log": self.open_liaison_unit_log,
            "liaison.agencies": self.open_liaison_agencies,
            "liaison.requests": self.open_liaison_requests,

            # ----- Public Information -----
            "public.unit_log": self.open_public_unit_log,
            "public.media_releases": self.open_public_media_releases,
            "public.inquiries": self.open_public_inquiries,

            # ----- Finance/Admin -----
            "finance.unit_log": self.open_finance_unit_log,
            "finance.time": self.open_finance_time,
            "finance.procurement": self.open_finance_procurement,
            "finance.summary": self.open_finance_summary,

            # ----- Toolkits -----
            "toolkit.sar.missing_person": self.open_toolkit_sar_missing_person,
            "toolkit.sar.pod": self.open_toolkit_sar_pod,
            "toolkit.disaster.damage": self.open_toolkit_disaster_damage,
            "toolkit.disaster.urban_interview": self.open_toolkit_disaster_urban_interview,
            "toolkit.disaster.photos": self.open_toolkit_disaster_photos,
            "planned.promotions": self.open_planned_promotions,
            "planned.vendors": self.open_planned_vendors,
            "planned.safety": self.open_planned_safety,
            "planned.tasking": self.open_planned_tasking,
            "planned.health_sanitation": self.open_planned_health_sanitation,
            "toolkit.initial.hasty": self.open_toolkit_initial_hasty,
            "toolkit.initial.reflex": self.open_toolkit_initial_reflex,

            # ----- Forms & Library -----
            "forms": self.open_forms,
            "library": self.open_reference_library,
            "help.user_guide": self.open_help_user_guide,

            # ----- Help -----
            "help.about": self.open_help_about,

            # ----- Window -----
            "window.home_dashboard": self.open_home_dashboard,
        }

        handler = handlers.get(key)
        if handler:
            handler()
        else:
            print(f"[OpenModule] no handler for {key}")

# ===== Part 4: Handlers in Menu Order (panel-factory pattern) ============
# --- 4.1 Menu ------------------------------------------------------------
    def open_menu_new_incident(self) -> None:
        from modules.incidents.new_incident_dialog import NewIncidentDialog

        dlg = NewIncidentDialog(self)
        dlg.created.connect(self._on_incident_created)
        dlg.show()

    def _on_incident_created(self, meta, db_path: str) -> None:
        """Handle mission creation from the New Incident dialog."""
        # 1) Register in master.db so it shows up in selectors
        try:
            from models.database import insert_new_incident, get_incident_by_number
            # Avoid duplicate records if one already exists
            if not get_incident_by_number(meta.number):
                insert_new_incident(
                    number=meta.number,
                    name=meta.name,
                    type=meta.type,
                    description=meta.description,
                    icp_location=meta.location,
                    is_training=meta.is_training,
                )
        except Exception as e:
            logger.exception("Failed to register incident in master.db: %s", e)
            QMessageBox.warning(
                self,
                "Database Error",
                f"Mission database created but failed to register in master.db:\n{e}",
            )

        # 2) Set as the active incident immediately
        try:
            from utils import incident_context
            self.current_incident_id = meta.number
            AppState.set_active_incident(meta.number)
            incident_context.set_active_incident(str(meta.number))
            self.update_title_with_active_incident()
        except Exception:
            logger.exception("Failed to set active incident context")

        # 3) Notify user (after attempting registration + activation)
        QMessageBox.information(
            self,
            "Mission Created",
            f"Mission '{meta.name}' created and activated.\nDB path: {db_path}",
        )

        # 4) If the incident selection window is open, refresh it and select
        if hasattr(self, "incident_selection_window") and hasattr(
            self.incident_selection_window, "reload_missions"
        ):
            try:
                self.incident_selection_window.reload_missions(select_slug=meta.slug())
            except Exception:
                logger.exception("Failed to refresh incident selection window")

        # --- 4.1 Menu ------------------------------------------------------------
    def open_menu_open_incident(self) -> None:
        """Launch the Incident Selection window."""
        from ui_bootstrap.incident_select_bootstrap import show_incident_selector
        def _apply_active(number: int) -> None:
            print(f"[main] on_select callback received: {number}")
            self.current_incident_id = number
            AppState.set_active_incident(number)
            self.update_title_with_active_incident()

        show_incident_selector(on_select=_apply_active)

    def open_menu_save_incident(self) -> None:
        from ui_bootstrap.incident_select_bootstrap import show_incident_selector
        show_incident_selector()

    def open_menu_settings(self) -> None:
        # Open the existing QML settings window (ApplicationWindow root) via QQuickView as a modal window
        from pathlib import Path
        from PySide6.QtQml import QQmlApplicationEngine

        engine = QQmlApplicationEngine()
        # Inject settings bridge so settings pages can read/write
        engine.rootContext().setContextProperty("settingsBridge", self.settings_bridge)

        qml_file = Path(__file__).resolve().parent / "qml" / "settingswindow.qml"
        engine.load(QUrl.fromLocalFile(str(qml_file)))

        if not engine.rootObjects():
            logger.error("Settings window failed to load: %s", qml_file)
            return

        win = engine.rootObjects()[0]
        # Tie to main window and make modal if possible
        try:
            if hasattr(win, "setTitle"):
                win.setTitle("Settings")
            if self.windowHandle() and hasattr(win, "setTransientParent"):
                win.setTransientParent(self.windowHandle())
            if hasattr(win, "setModality"):
                win.setModality(Qt.ApplicationModal)
            if hasattr(win, "show"):
                win.show()
        except Exception:
            pass

        # Keep references alive
        if not hasattr(self, "_open_qml_engines"):
            self._open_qml_engines = []
        if not hasattr(self, "_open_qml_windows"):
            self._open_qml_windows = []
        self._open_qml_engines.append(engine)
        self._open_qml_windows.append(win)

    def open_menu_exit(self) -> None:
        # Exit remains a direct action rather than opening a panel.
        QApplication.instance().quit()

# --- 4.2 Edit ------------------------------------------------------------
    def open_edit_ems(self) -> None:
        self._open_qml_modal("qml/EmsWindow.qml", title="EMS Agencies")

    def open_edit_hospitals(self) -> None:
        self._open_qml_modal("qml/HospitalsWindow.qml", title="Hospitals")

    def open_edit_canned_comm_entries(self) -> None:
        self._open_qml_modal("qml/CannedCommEntriesWindow.qml", title="Canned Communication Entries")

    def open_edit_personnel(self) -> None:
        self._open_qml_modal("qml/PersonnelWindow.qml", title="Personnel")

    def open_edit_objectives(self) -> None:
        self._open_qml_modal("qml/ObjectivesWindow.qml", title="Objectives")

    def open_edit_task_types(self) -> None:
        self._open_qml_modal("qml/TaskTypesWindow.qml", title="Task Types")

    def open_edit_team_types(self) -> None:
        self._open_qml_modal("qml/TeamTypesWindow.qml", title="Team Types")

    def open_edit_vehicles(self) -> None:
        self._open_qml_modal("qml/VehiclesWindow.qml", title="Vehicles")

    def open_edit_aircraft(self) -> None:
        self._open_qml_modal("qml/AircraftWindow.qml", title="Aircraft")

    def open_edit_equipment(self) -> None:
        self._open_qml_modal("qml/EquipmentWindow.qml", title="Equipment")

    def open_edit_comms_resources(self) -> None:
        self._open_qml_modal("qml/CommsResourcesWindow.qml", title="Communications Resources (ICS-217)")

    def open_edit_safety_templates(self) -> None:
        self._open_qml_modal("qml/SafetyTemplatesWindow.qml", title="Incident Safety Analysis (ICS-215A)")

# --- 4.3 Command ---------------------------------------------------------
    def open_command_unit_log(self) -> None:
        from modules import ics214
        incident_id = getattr(self, "current_incident_id", None)
        panel = ics214.get_ics214_panel(incident_id)
        self._open_dock_widget(panel, title="ICS-214 Activity Log")

    def open_command_incident_overview(self) -> None:
        from modules import command
        incident_id = getattr(self, "current_incident_id", None)
        panel = command.get_incident_overview_panel(incident_id)
        self._open_dock_widget(panel, title="Incident Overview")

    def open_command_iap(self) -> None:
        from modules import command
        incident_id = getattr(self, "current_incident_id", None)
        panel = command.get_iap_builder_panel(incident_id)
        self._open_dock_widget(panel, title="Incident Action Plan Builder")

    def open_command_objectives(self) -> None:
        from modules import command
        incident_id = getattr(self, "current_incident_id", None)
        panel = command.get_objectives_panel(incident_id)
        self._open_dock_widget(panel, title="Incident Objectives (ICS 202)")

    def open_command_staff_org(self) -> None:
        from modules import command
        incident_id = getattr(self, "current_incident_id", None)
        panel = command.get_staff_org_panel(incident_id)
        self._open_dock_widget(panel, title="Command Staff Organization (ICS 203)")

    def open_command_sitrep(self) -> None:
        from modules import command
        incident_id = getattr(self, "current_incident_id", None)
        panel = command.get_sitrep_panel(incident_id)
        self._open_dock_widget(panel, title="Situation Report (ICS 209)")

# --- 4.4 Planning --------------------------------------------------------
    def open_planning_unit_log(self) -> None:
        from modules import ics214
        incident_id = getattr(self, "current_incident_id", None)
        panel = ics214.get_ics214_panel(incident_id)
        self._open_dock_widget(panel, title="ICS-214 Activity Log")

    def open_planning_dashboard(self) -> None:
        from modules import planning
        incident_id = getattr(self, "current_incident_id", None)
        panel = planning.get_dashboard_panel(incident_id)
        self._open_dock_widget(panel, title="Planning Dashboard")

    def open_planning_approvals(self) -> None:
        from modules import planning
        incident_id = getattr(self, "current_incident_id", None)
        panel = planning.get_approvals_panel(incident_id)
        self._open_dock_widget(panel, title="Pending Approvals")

    def open_planning_forecast(self) -> None:
        from modules import planning
        incident_id = getattr(self, "current_incident_id", None)
        panel = planning.get_forecast_panel(incident_id)
        self._open_dock_widget(panel, title="Planning Forecast")

    def open_planning_op_manager(self) -> None:
        from modules import planning
        incident_id = getattr(self, "current_incident_id", None)
        panel = planning.get_op_manager_panel(incident_id)
        self._open_dock_widget(panel, title="Operational Period Manager")

    def open_planning_taskmetrics(self) -> None:
        from modules import planning
        incident_id = getattr(self, "current_incident_id", None)
        panel = planning.get_taskmetrics_panel(incident_id)
        self._open_dock_widget(panel, title="Task Metrics Dashboard")

    def open_planning_strategic_objectives(self) -> None:
        from modules import planning
        incident_id = getattr(self, "current_incident_id", None)
        panel = planning.get_strategic_objectives_panel(incident_id)
        self._open_dock_widget(panel, title="Strategic Objective Tracker")

    def open_planning_sitrep(self) -> None:
        from modules import planning
        incident_id = getattr(self, "current_incident_id", None)
        panel = planning.get_sitrep_panel(incident_id)
        self._open_dock_widget(panel, title="Situation Report")

# --- 4.5 Operations ------------------------------------------------------
    def open_operations_unit_log(self) -> None:
        from modules import ics214
        incident_id = getattr(self, "current_incident_id", None)
        panel = ics214.get_ics214_panel(incident_id)
        self._open_dock_widget(panel, title="ICS-214 Activity Log")

    def open_operations_dashboard(self) -> None:
        from modules import operations
        incident_id = getattr(self, "current_incident_id", None)
        panel = operations.get_dashboard_panel(incident_id)
        self._open_dock_widget(panel, title="Assignments Dashboard")

    def open_operations_team_assignments(self) -> None:
        from modules import operations
        incident_id = getattr(self, "current_incident_id", None)
        panel = operations.get_team_assignments_panel(incident_id)
        self._open_dock_widget(panel, title="Team Assignments")

    def open_operations_team_status(self) -> None:
        # Prefer the QWidget panel version to avoid QQuickWidget rendering issues
        try:
            from modules.operations.panels.team_status_panel import TeamStatusPanel
            panel = TeamStatusPanel(self)
            self._open_dock_widget(panel, title="Team Status")
            return
        except Exception:
            pass
        # Fallback to QML if panel import fails (prefer QQuickView container)
        from data.sample_data import TEAM_ROWS, TEAM_HEADERS
        qml_file = os.path.join("modules", "operations", "qml", "TeamStatus.qml")
        ctx = {"teamRows": TEAM_ROWS, "teamHeaders": TEAM_HEADERS, "statusColumn": 4}
        self._open_dock_from_qml_view(qml_file, "Team Status", context=ctx)

    def open_operations_task_board(self) -> None:
        # Prefer the QWidget panel version to avoid QQuickWidget rendering issues
        try:
            from modules.operations.panels.task_status_panel import TaskStatusPanel
            panel = TaskStatusPanel(self)
            self._open_dock_widget(panel, title="Task Status")
            return
        except Exception:
            pass
        # Fallback to QML if panel import fails (prefer QQuickView container)
        from data.sample_data import TASK_ROWS, TASK_HEADERS
        qml_file = os.path.join("modules", "operations", "qml", "TaskStatus.qml")
        try:
            status_idx = TASK_HEADERS.index("Status")
        except ValueError:
            status_idx = 2
        ctx = {"taskRows": TASK_ROWS, "taskHeaders": TASK_HEADERS, "statusColumn": status_idx}
        self._open_dock_from_qml_view(qml_file, "Task Board", context=ctx)

    def open_operations_narrative(self) -> None:
        # Open the narrative window (incident-scoped)
        self._open_qml_modal("qml/NarrativeWindow.qml", title="Narrative")

    # Debug helpers to open QML boards directly (QQuickView)
    def _open_team_status_qml_debug(self) -> None:
        from data.sample_data import TEAM_ROWS, TEAM_HEADERS
        qml_file = os.path.join("modules", "operations", "qml", "TeamStatus.qml")
        ctx = {"teamRows": TEAM_ROWS, "teamHeaders": TEAM_HEADERS, "statusColumn": 4}
        self._open_dock_from_qml_view(qml_file, "Team Status (QML)", context=ctx)

    def _open_task_status_qml_debug(self) -> None:
        from data.sample_data import TASK_ROWS, TASK_HEADERS
        qml_file = os.path.join("modules", "operations", "qml", "TaskStatus.qml")
        try:
            status_idx = TASK_HEADERS.index("Status")
        except ValueError:
            status_idx = 2
        ctx = {"taskRows": TASK_ROWS, "taskHeaders": TASK_HEADERS, "statusColumn": status_idx}
        self._open_dock_from_qml_view(qml_file, "Task Status (QML)", context=ctx)

# --- 4.6 Logistics -------------------------------------------------------
    def open_logistics_unit_log(self) -> None:
        from modules import ics214
        incident_id = getattr(self, "current_incident_id", None)
        panel = ics214.get_ics214_panel(incident_id)
        self._open_dock_widget(panel, title="ICS-214 Activity Log")

    def open_logistics_dashboard(self) -> None:
        from modules import logistics
        incident_id = getattr(self, "current_incident_id", None)
        panel = logistics.get_logistics_panel(incident_id)
        self._open_dock_widget(panel, title="Logistics Dashboard")

    def open_logistics_211(self) -> None:
        from modules import logistics
        incident_id = getattr(self, "current_incident_id", None)
        panel = logistics.get_checkin_panel(incident_id)
        self._open_dock_widget(panel, title="Check-In (ICS-211)")

    def open_logistics_requests(self) -> None:
        from modules import logistics
        incident_id = getattr(self, "current_incident_id", None)
        panel = logistics.get_requests_panel(incident_id)
        self._open_dock_widget(panel, title="Resource Requests")

    def open_logistics_equipment(self) -> None:
        from modules import logistics
        incident_id = getattr(self, "current_incident_id", None)
        panel = logistics.get_equipment_panel(incident_id)
        self._open_dock_widget(panel, title="Equipment Inventory")

    def open_logistics_213rr(self) -> None:
        from modules import logistics
        incident_id = getattr(self, "current_incident_id", None)
        panel = logistics.get_213rr_panel(incident_id)
        self._open_dock_widget(panel, title="Resource Request (ICS-213RR)")

# --- 4.7 Communications --------------------------------------------------
    def open_comms_unit_log(self) -> None:
        from modules import ics214
        incident_id = getattr(self, "current_incident_id", None)
        panel = ics214.get_ics214_panel(incident_id)
        self._open_dock_widget(panel, title="ICS-214 Activity Log")

    def open_comms_chat(self) -> None:
        from modules.communications.panels import MessageLogPanel

        # TODO: incident-specific scoping for communications panels
        _incident_id = getattr(self, "current_incident_id", None)
        panel = MessageLogPanel()
        self._open_dock_widget(panel, title="Messaging")

    def open_comms_213(self) -> None:
        from modules.communications.panels import MessageLogPanel

        # TODO: incident-specific scoping for communications panels
        _incident_id = getattr(self, "current_incident_id", None)
        panel = MessageLogPanel()
        self._open_dock_widget(panel, title="ICS 213 Messages")

    def open_comms_205(self) -> None:
        from modules.communications.panels import RadioPlanBuilder

        # TODO: incident-specific scoping for communications panels
        _incident_id = getattr(self, "current_incident_id", None)
        panel = RadioPlanBuilder()
        self._open_dock_widget(panel, title="Communications Plan (ICS-205)")

# --- 4.8 Intel -----------------------------------------------------------
    def open_intel_unit_log(self) -> None:
        from modules import ics214
        incident_id = getattr(self, "current_incident_id", None)
        panel = ics214.get_ics214_panel(incident_id)
        self._open_dock_widget(panel, title="ICS-214 Activity Log")

    def open_intel_dashboard(self) -> None:
        from modules import intel
        incident_id = getattr(self, "current_incident_id", None)
        panel = intel.get_dashboard_panel(incident_id)
        self._open_dock_widget(panel, title="Intel Dashboard")

    def open_intel_clue_log(self) -> None:
        from modules import intel
        incident_id = getattr(self, "current_incident_id", None)
        panel = intel.get_clue_log_panel(incident_id)
        self._open_dock_widget(panel, title="Clue Log (SAR-134)")

    def open_intel_add_clue(self) -> None:
        from modules import intel
        incident_id = getattr(self, "current_incident_id", None)
        panel = intel.get_add_clue_panel(incident_id)
        self._open_dock_widget(panel, title="Add Clue (SAR-135)")

# --- 4.9 Medical & Safety -----------------------------------------------
    def open_medical_unit_log(self) -> None:
        from modules import ics214
        incident_id = getattr(self, "current_incident_id", None)
        panel = ics214.get_ics214_panel(incident_id)
        self._open_dock_widget(panel, title="ICS-214 Activity Log")

    def open_safety_unit_log(self) -> None:
        from modules import ics214
        incident_id = getattr(self, "current_incident_id", None)
        panel = ics214.get_ics214_panel(incident_id)
        self._open_dock_widget(panel, title="ICS-214 Activity Log")

    def open_medical_206(self) -> None:
        from modules import medical
        incident_id = getattr(self, "current_incident_id", None)
        panel = medical.get_206_panel(incident_id)
        self._open_dock_widget(panel, title="Medical Plan (ICS 206)")

    def open_safety_208(self) -> None:
        from modules import safety
        incident_id = getattr(self, "current_incident_id", None)
        panel = safety.get_208_panel(incident_id)
        self._open_dock_widget(panel, title="Safety Message (ICS-208)")

    def open_safety_215A(self) -> None:
        from modules import safety
        incident_id = getattr(self, "current_incident_id", None)
        panel = safety.get_215A_panel(incident_id)
        self._open_dock_widget(panel, title="Incident Safety Analysis (ICS-215A)")

    def open_safety_caporm(self) -> None:
        from modules import safety
        incident_id = getattr(self, "current_incident_id", None)
        panel = safety.get_caporm_panel(incident_id)
        self._open_dock_widget(panel, title="CAP ORM")

# --- 4.10 Liaison --------------------------------------------------------
    def open_liaison_unit_log(self) -> None:
        from modules import ics214
        incident_id = getattr(self, "current_incident_id", None)
        panel = ics214.get_ics214_panel(incident_id)
        self._open_dock_widget(panel, title="ICS-214 Activity Log")

    def open_liaison_agencies(self) -> None:
        from modules import liaison
        incident_id = getattr(self, "current_incident_id", None)
        panel = liaison.get_agencies_panel(incident_id)
        self._open_dock_widget(panel, title="Agency Directory")

    def open_liaison_requests(self) -> None:
        from modules import liaison
        incident_id = getattr(self, "current_incident_id", None)
        panel = liaison.get_requests_panel(incident_id)
        self._open_dock_widget(panel, title="Customer Requests")

# --- 4.11 Public Information --------------------------------------------
    def open_public_unit_log(self) -> None:
        from modules import ics214
        incident_id = getattr(self, "current_incident_id", None)
        panel = ics214.get_ics214_panel(incident_id)
        self._open_dock_widget(panel, title="ICS-214 Activity Log")

    def open_public_media_releases(self) -> None:
        from modules import public_info
        incident_id = getattr(self, "current_incident_id", None)
        panel = public_info.get_media_releases_panel(incident_id)
        self._open_dock_widget(panel, title="Media Releases")

    def open_public_inquiries(self) -> None:
        from modules import public_info
        incident_id = getattr(self, "current_incident_id", None)
        panel = public_info.get_inquiries_panel(incident_id)
        self._open_dock_widget(panel, title="Public Inquiries")

# --- 4.12 Finance/Admin --------------------------------------------------
    def open_finance_unit_log(self) -> None:
        from modules import ics214
        incident_id = getattr(self, "current_incident_id", None)
        panel = ics214.get_ics214_panel(incident_id)
        self._open_dock_widget(panel, title="ICS-214 Activity Log")

    def open_finance_time(self) -> None:
        from modules import finance
        incident_id = getattr(self, "current_incident_id", None)
        panel = finance.get_time_panel(incident_id)
        self._open_dock_widget(panel, title="Time Tracking")

    def open_finance_procurement(self) -> None:
        from modules import finance
        incident_id = getattr(self, "current_incident_id", None)
        panel = finance.get_procurement_panel(incident_id)
        self._open_dock_widget(panel, title="Expenses && Procurement")

    def open_finance_summary(self) -> None:
        from modules import finance
        incident_id = getattr(self, "current_incident_id", None)
        panel = finance.get_summary_panel(incident_id)
        self._open_dock_widget(panel, title="Cost Summary")

# --- 4.13 Toolkits -------------------------------------------------------
    def open_toolkit_sar_missing_person(self) -> None:
        from modules.sartoolkit import sar
        incident_id = getattr(self, "current_incident_id", None)
        panel = sar.get_missing_person_panel(incident_id)
        self._open_dock_widget(panel, title="Missing Person Toolkit")

    def open_toolkit_sar_pod(self) -> None:
        from modules.sartoolkit import sar
        incident_id = getattr(self, "current_incident_id", None)
        panel = sar.get_pod_panel(incident_id)
        self._open_dock_widget(panel, title="POD Calculator")

    def open_toolkit_disaster_damage(self) -> None:
        from modules.disasterresponse import disaster
        incident_id = getattr(self, "current_incident_id", None)
        panel = disaster.get_damage_panel(incident_id)
        self._open_dock_widget(panel, title="Damage Assessment")

    def open_toolkit_disaster_urban_interview(self) -> None:
        from modules.disasterresponse import disaster
        incident_id = getattr(self, "current_incident_id", None)
        panel = disaster.get_urban_interview_panel(incident_id)
        self._open_dock_widget(panel, title="Urban Interview Log")

    def open_toolkit_disaster_photos(self) -> None:
        from modules.disasterresponse import disaster
        incident_id = getattr(self, "current_incident_id", None)
        panel = disaster.get_photos_panel(incident_id)
        self._open_dock_widget(panel, title="Damage Photos")

    def open_planned_promotions(self) -> None:
        from modules import plannedtoolkit
        incident_id = getattr(self, "current_incident_id", None)
        panel = plannedtoolkit.get_promotions_panel(incident_id)
        self._open_dock_widget(panel, title="External Messaging")

    def open_planned_vendors(self) -> None:
        from modules import plannedtoolkit
        incident_id = getattr(self, "current_incident_id", None)
        panel = plannedtoolkit.get_vendors_panel(incident_id)
        self._open_dock_widget(panel, title="Vendors && Permits")

    def open_planned_safety(self) -> None:
        from modules import plannedtoolkit
        incident_id = getattr(self, "current_incident_id", None)
        panel = plannedtoolkit.get_safety_panel(incident_id)
        self._open_dock_widget(panel, title="Public Safety")

    def open_planned_tasking(self) -> None:
        from modules import plannedtoolkit
        incident_id = getattr(self, "current_incident_id", None)
        panel = plannedtoolkit.get_tasking_panel(incident_id)
        self._open_dock_widget(panel, title="Tasking && Assignments")

    def open_planned_health_sanitation(self) -> None:
        from modules import plannedtoolkit
        incident_id = getattr(self, "current_incident_id", None)
        panel = plannedtoolkit.get_health_sanitation_panel(incident_id)
        self._open_dock_widget(panel, title="Health && Sanitation")

    def open_toolkit_initial_hasty(self) -> None:
        from modules.initialresponse import initial
        incident_id = getattr(self, "current_incident_id", None)
        panel = initial.get_hasty_panel(incident_id)
        self._open_dock_widget(panel, title="Hasty Tools")

    def open_toolkit_initial_reflex(self) -> None:
        from modules.initialresponse import initial
        incident_id = getattr(self, "current_incident_id", None)
        panel = initial.get_reflex_panel(incident_id)
        self._open_dock_widget(panel, title="Reflex Taskings")

# --- 4.14 Resources (Forms & Library) -----------------------------------
    def open_forms(self) -> None:
        from modules import referencelibrary
        incident_id = getattr(self, "current_incident_id", None)
        panel = referencelibrary.get_form_library_panel(incident_id)
        self._open_dock_widget(panel, title="Form Library")

    def open_reference_library(self) -> None:
        from modules import referencelibrary
        incident_id = getattr(self, "current_incident_id", None)
        panel = referencelibrary.get_library_panel()
        self._open_dock_widget(panel, title="Reference Library")

    def open_help_user_guide(self) -> None:
        from modules import referencelibrary
        incident_id = getattr(self, "current_incident_id", None)
        panel = referencelibrary.get_user_guide_panel(incident_id)
        self._open_dock_widget(panel, title="User Guide")

# --- 4.15 Help -----------------------------------------------------------
    def open_help_about(self) -> None:
        from modules import referencelibrary
        incident_id = getattr(self, "current_incident_id", None)
        panel = referencelibrary.get_about_panel(incident_id)
        self._open_dock_widget(panel, title="About SARApp")

# ===== Part 5: Shared Windows, Helpers & Utilities =======================
    def _open_dock_widget(self, widget: QWidget, title: str, float_on_open: bool | None = True) -> None:
        """Embed widget in an ADS dock panel.
        By default, menu-launched panels open floating (undocked). Use float_on_open=False to dock.
        """
        dock = CDockWidget(self.dock_manager, title)
        dock.setWidget(widget)
        if float_on_open:
            # Preferred: directly add as floating if ADS supports it
            try:
                self.dock_manager.addDockWidgetFloating(dock)  # type: ignore[attr-defined]
                dock.show()
                return
            except Exception:
                pass
            # Alternate: create an explicit floating container
            try:
                container = self.dock_manager.createFloatingDockContainer(dock)  # type: ignore[attr-defined]
                try:
                    from PySide6.QtGui import QCursor
                    container.move(QCursor.pos())  # type: ignore[attr-defined]
                except Exception:
                    pass
                try:
                    container.show()  # type: ignore[attr-defined]
                except Exception:
                    pass
                return
            except Exception:
                # Fallback: add then toggle floating
                area = CenterDockWidgetArea if not self.findChildren(CDockWidget) else LeftDockWidgetArea
                self.dock_manager.addDockWidget(area, dock)
                try:
                    dock.setFloating(True)
                except Exception:
                    pass
                dock.show()
                return
        # Docked open
        area = CenterDockWidgetArea if not self.findChildren(CDockWidget) else LeftDockWidgetArea
        self.dock_manager.addDockWidget(area, dock)
        dock.show()

    def _open_dock_from_qml_view(self, qml_rel_path: str, title: str, float_on_open: bool | None = True, context: dict | None = None) -> None:
        """Open QML using QQuickView + QWidget::createWindowContainer to avoid QQuickWidget text issues."""
        try:
            view = QQuickView()
        except Exception:
            # Fallback to original path if QQuickView unavailable
            self._open_dock_from_qml(qml_rel_path, title, float_on_open=float_on_open, context=context)
            return
        try:
            view.setResizeMode(QQuickView.SizeRootObjectToView)
        except Exception:
            pass
        try:
            if context:
                ctx = view.rootContext()
                for k, v in context.items():
                    ctx.setContextProperty(k, v)
        except Exception:
            pass
        view.setSource(QUrl.fromLocalFile(os.path.abspath(qml_rel_path)))
        container = QWidget.createWindowContainer(view)
        try:
            container.setMinimumSize(200, 120)
            container.setFocusPolicy(Qt.StrongFocus)
        except Exception:
            pass
        dock = CDockWidget(self.dock_manager, title)
        dock.setWidget(container)
        if float_on_open:
            try:
                self.dock_manager.addDockWidgetFloating(dock)  # type: ignore[attr-defined]
                dock.show()
                return
            except Exception:
                pass
        area = CenterDockWidgetArea if not self.findChildren(CDockWidget) else LeftDockWidgetArea
        self.dock_manager.addDockWidget(area, dock)
        dock.show()

    def _open_dock_from_qml(self, qml_rel_path: str, title: str, float_on_open: bool | None = True, context: dict | None = None) -> None:
        widget = QQuickWidget()
        widget.setResizeMode(QQuickWidget.SizeRootObjectToView)
        try:
            if context:
                # Use QQuickWidget.rootContext() so properties are visible to this component
                ctx = widget.rootContext()
                for k, v in context.items():
                    ctx.setContextProperty(k, v)
        except Exception:
            pass
        widget.setSource(QUrl.fromLocalFile(os.path.abspath(qml_rel_path)))
        dock = CDockWidget(self.dock_manager, title)
        dock.setWidget(widget)
        if float_on_open:
            # Preferred: add as floating
            try:
                self.dock_manager.addDockWidgetFloating(dock)  # type: ignore[attr-defined]
                dock.show()
                return
            except Exception:
                pass
            # Alternate: floating container
            try:
                container = self.dock_manager.createFloatingDockContainer(dock)  # type: ignore[attr-defined]
                try:
                    from PySide6.QtGui import QCursor
                    container.move(QCursor.pos())  # type: ignore[attr-defined]
                except Exception:
                    pass
                try:
                    container.show()  # type: ignore[attr-defined]
                except Exception:
                    pass
                return
            except Exception:
                area = CenterDockWidgetArea if not self.findChildren(CDockWidget) else LeftDockWidgetArea
                self.dock_manager.addDockWidget(area, dock)
                try:
                    dock.setFloating(True)
                except Exception:
                    pass
                dock.show()
                return
        area = CenterDockWidgetArea if not self.findChildren(CDockWidget) else LeftDockWidgetArea
        self.dock_manager.addDockWidget(area, dock)
        dock.show()

    def _open_qml_modal(self, qml_rel_path: str, title: str) -> None:
        """Open a QML Window (as a modal dialog) and inject the catalog bridge.

        This is used by Edit > Master Catalog windows (EMS, Hospitals, etc.).
        """
        view = QQuickView()
        view.setTitle(title)
        try:
            view.setResizeMode(QQuickView.SizeRootObjectToView)
        except Exception:
            pass

        # Create/reuse a shared CatalogBridge for master catalog windows
        if not hasattr(self, "_catalog_bridge"):
            self._catalog_bridge = CatalogBridge(db_path="data/master.db")

        # Expose bridges and models to QML
        ctx = view.rootContext()
        ctx.setContextProperty("catalogBridge", self._catalog_bridge)
<<<<<<< ours
        ctx.setContextProperty("teamStatuses", TEAM_STATUSES)
=======

        base = os.path.basename(qml_rel_path)
        if base == "CannedCommEntriesWindow.qml":
            try:
                from utils.constants import TEAM_STATUSES
                ctx.setContextProperty("teamStatuses", TEAM_STATUSES)
            except Exception:
                pass

>>>>>>> theirs
        # Incident bridge (incident-scoped CRUD)
        try:
            if not hasattr(self, "_incident_bridge"):
                self._incident_bridge = IncidentBridge()
            ctx.setContextProperty("incidentBridge", self._incident_bridge)
        except Exception as e:
            print("[main] IncidentBridge init failed:", e)

        # Inject a per-window SqliteTableModel when we can map the window to a table
        try:
            # Strip the full suffix "Window.qml" (10 chars) to get the base name
            name = base[:-10] if base.endswith("Window.qml") else os.path.splitext(base)[0]
            table = self._resolve_master_table(name)
            print(f"[main._open_qml_modal] qml='{qml_rel_path}', base='{base}', name='{name}', resolved_table='{table}'")
            if table:
                model_name = f"{name}Model"
                model = SqliteTableModel("data/master.db")
                sql = f"SELECT * FROM {table}"
                print(f"[main._open_qml_modal] injecting model '{model_name}' with sql: {sql}")
                model.load_query(sql)
                ctx.setContextProperty(model_name, model)
                try:
                    print(f"[main._open_qml_modal] model '{model_name}' rowCount={model.rowCount()}")
                except Exception:
                    pass
            elif name == "Narrative":
                # Inject incident-scoped model for narrative
                try:
                    from utils import incident_context
                    db_path = str(incident_context.get_active_incident_db_path())
                    model_name = "NarrativeModel"
                    model = SqliteTableModel(db_path)
                    sql = "SELECT id, taskid, timestamp, narrative, entered_by, team_num, critical FROM narrative_entries ORDER BY timestamp DESC"
                    print(f"[main._open_qml_modal] injecting INCIDENT model '{model_name}' with sql: {sql}")
                    model.load_query(sql)
                    ctx.setContextProperty(model_name, model)
                except Exception as e:
                    print("[main._open_qml_modal] failed to inject NarrativeModel:", e)
            else:
                # Log available tables to aid debugging
                try:
                    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "master.db")
                    con = sqlite3.connect(db_path)
                    cur = con.cursor()
                    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tbls = [r[0] for r in cur.fetchall()]
                    con.close()
                    print(f"[main._open_qml_modal] no table for '{name}'. sqlite tables: {tbls}")
                except Exception as e:
                    print(f"[main._open_qml_modal] failed to enumerate tables: {e}")
        except Exception as e:
            print(f"[main] model injection error for {qml_rel_path}: {e}")

        from pathlib import Path
        qml_file = Path(__file__).resolve().parent / qml_rel_path
        view.setSource(QUrl.fromLocalFile(str(qml_file)))
        view.show()
        if not hasattr(self, "_open_qml_views"):
            self._open_qml_views = []
        self._open_qml_views.append(view)

    def _resolve_master_table(self, base_name: str) -> str | None:
        """Resolve a master.db table name for a given Window base name.
        Uses sqlite_master to confirm existence and tries sensible mappings,
        including canonical names from master_catalog where applicable.
        """
        # List all tables from master.db
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "master.db")
        tables: set[str] = set()
        try:
            con = sqlite3.connect(db_path)
            cur = con.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {r[0] for r in cur.fetchall()}
            con.close()
        except Exception as e:
            print(f"[main] _resolve_master_table: unable to read tables: {e}")
            return None

        # Canonical known mappings
        canonical = {
            "Personnel": "personnel",
            "Vehicles": "vehicles",
            "Aircraft": "aircraft",
            "Equipment": "equipment",
            "CommsResources": "comms_resources",
            "Objectives": "incident_objectives",
            "Certifications": "certification_types",
            "TeamTypes": "team_types",
            "TaskTypes": "task_types",
            "CannedCommEntries": "canned_comm_entries",
            "Ems": "ems",
            "Hospitals": "ems",  # window displays EMS-style contacts
            "SafetyTemplates": "safety_templates",
        }

        # 1) Try canonical mapping
        tbl = canonical.get(base_name)
        if tbl and tbl in tables:
            return tbl

        # 2) Try snake_case of base name
        import re
        snake = re.sub(r"(?<!^)([A-Z])", r"_\1", base_name).lower()
        if snake in tables:
            return snake

        # 3) Try simple lowercase/plural checks
        low = base_name.lower()
        if low in tables:
            return low
        if f"{low}s" in tables:
            return f"{low}s"

        # 4) Nothing matched
        return None

    def closeEvent(self, event) -> None:  # type: ignore[override]
        # Save perspectives via QSettings to match ADS API
        try:
            self.dock_manager.addPerspective("default")
            settings_obj = QSettings(self._perspective_file, QSettings.IniFormat)
            self.dock_manager.savePerspectives(settings_obj)
        except Exception as e:
            logger.warning("Failed to save ADS perspectives: %s", e)
        super().closeEvent(event)

    def _create_default_docks(self) -> None:
        """Create a few sample docks (Mission Status, Team Status, Task Status)."""
        # Use full-featured panels for default docks
        try:
            from modules.operations.panels.team_status_panel import TeamStatusPanel
        except Exception:
            TeamStatusPanel = None  # type: ignore
        try:
            from modules.operations.panels.task_status_panel import TaskStatusPanel
        except Exception:
            TaskStatusPanel = None  # type: ignore

        # Mission Status dock uses the active_incident_label prepared in __init__
        status_container = QWidget()
        status_layout = QVBoxLayout(status_container)
        status_layout.setContentsMargins(8, 8, 8, 8)
        status_layout.addWidget(self.active_incident_label)
        # Make Mission Status the central area so other docks can dock around the window
        status_dock = CDockWidget(self.dock_manager, "Mission Status")
        status_dock.setWidget(status_container)
        self.dock_manager.addDockWidget(CenterDockWidgetArea, status_dock)
        status_dock.show()

        # Optional sample boards: prefer QWidget panels; fallback to QML
        if TeamStatusPanel:
            try:
                team_panel = TeamStatusPanel(self)
                team_dock = CDockWidget(self.dock_manager, "Team Status")
                team_dock.setWidget(team_panel)
                self.dock_manager.addDockWidget(LeftDockWidgetArea, team_dock)
                team_dock.show()
            except Exception:
                pass
        else:
            try:
                from data.sample_data import TEAM_ROWS, TEAM_HEADERS
                qml_team = os.path.join("modules", "operations", "qml", "TeamStatus.qml")
                team_ctx = {"teamRows": TEAM_ROWS, "teamHeaders": TEAM_HEADERS, "statusColumn": 4}
                self._open_dock_from_qml_view(qml_team, "Team Status", float_on_open=False, context=team_ctx)
            except Exception:
                pass

        if TaskStatusPanel:
            try:
                task_panel = TaskStatusPanel(self)
                task_dock = CDockWidget(self.dock_manager, "Task Status")
                task_dock.setWidget(task_panel)
                self.dock_manager.addDockWidget(BottomDockWidgetArea, task_dock)
                task_dock.show()
            except Exception:
                pass
        else:
            try:
                from data.sample_data import TASK_ROWS, TASK_HEADERS
                qml_task = os.path.join("modules", "operations", "qml", "TaskStatus.qml")
                try:
                    status_idx = TASK_HEADERS.index("Status")
                except ValueError:
                    status_idx = 2
                task_ctx = {"taskRows": TASK_ROWS, "taskHeaders": TASK_HEADERS, "statusColumn": status_idx}
                self._open_dock_from_qml_view(qml_task, "Task Status", float_on_open=False, context=task_ctx)
            except Exception:
                pass

    def open_new_workspace_window(self) -> None:
        """Create a blank floating dock window you can move to another monitor.
        Other panels can be docked into it by dragging.
        """
        # Minimal placeholder instructing the user
        placeholder_widget = QWidget()
        v = QVBoxLayout(placeholder_widget)
        v.setContentsMargins(24, 24, 24, 24)
        lbl = QLabel("Drop panels here")
        v.addWidget(lbl)

        placeholder = CDockWidget(self.dock_manager, "Workspace")
        placeholder.setWidget(placeholder_widget)

        # Prefer creating a true floating dock container if ADS supports it
        try:
            container = self.dock_manager.createFloatingDockContainer(placeholder)  # type: ignore[attr-defined]
            try:
                from PySide6.QtGui import QCursor
                container.move(QCursor.pos())  # type: ignore[attr-defined]
            except Exception:
                pass
            try:
                container.show()  # type: ignore[attr-defined]
            except Exception:
                pass
        except Exception:
            # Fallback: add and float the placeholder dock itself
            self.dock_manager.addDockWidget(LeftDockWidgetArea, placeholder)
            try:
                placeholder.setFloating(True)
            except Exception:
                pass
            placeholder.show()

        if TaskStatusPanel:
            try:
                task_panel = TaskStatusPanel(self)
                task_dock = CDockWidget(self.dock_manager, "Task Status")
                task_dock.setWidget(task_panel)
                self.dock_manager.addDockWidget(BottomDockWidgetArea, task_dock)
                task_dock.show()
            except Exception:
                pass

    def _reset_layout(self) -> None:
        """Clear current perspectives and rebuild default docks."""
        try:
            # Try to remove perspectives by saving empty
            settings_obj = QSettings(self._perspective_file, QSettings.IniFormat)
            # Overwrite with nothing and clear the file
            settings_obj.clear()
        except Exception:
            pass
        # Remove existing dock widgets (best-effort)
        for dw in list(self.findChildren(CDockWidget)):
            try:
                dw.close()
                dw.deleteLater()
            except Exception:
                pass
        self._create_default_docks()

    def open_display_templates_dialog(self) -> None:
        """Open a modal dialog to manage dock layout templates (ADS perspectives)."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Display Templates")
        v = QVBoxLayout(dlg)

        # List available perspectives
        lst = QListWidget(dlg)
        perspective_names = []
        try:
            perspective_names = list(self.dock_manager.perspectiveNames())
        except Exception:
            perspective_names = []
        for name in perspective_names:
            lst.addItem(name)
        v.addWidget(lst)

        # Buttons: Load, Save As, Delete, Close
        btn_row = QHBoxLayout()
        btn_load = QPushButton("Load")
        btn_save = QPushButton("Save As…")
        btn_delete = QPushButton("Delete")
        btn_close = QPushButton("Close")
        btn_row.addWidget(btn_load)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_delete)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_close)
        v.addLayout(btn_row)

        def refresh_list():
            lst.clear()
            try:
                names = list(self.dock_manager.perspectiveNames())
            except Exception:
                names = []
            for nm in names:
                lst.addItem(nm)

        def persist_perspectives():
            try:
                settings_obj = QSettings(self._perspective_file, QSettings.IniFormat)
                self.dock_manager.savePerspectives(settings_obj)
            except Exception:
                pass

        def on_load():
            item = lst.currentItem()
            if not item:
                return
            name = item.text()
            try:
                self.dock_manager.openPerspective(name)
            except Exception:
                # Fallback: try reloading from disk first then open
                try:
                    settings_obj = QSettings(self._perspective_file, QSettings.IniFormat)
                    self.dock_manager.loadPerspectives(settings_obj)
                    self.dock_manager.openPerspective(name)
                except Exception:
                    QMessageBox.warning(dlg, "Load Failed", f"Could not load template '{name}'.")

        def on_save():
            name, ok = QInputDialog.getText(dlg, "Save Template", "Template name:")
            if not ok or not str(name).strip():
                return
            name = str(name).strip()
            try:
                # If name exists, remove before adding to overwrite
                try:
                    self.dock_manager.removePerspective(name)
                except Exception:
                    pass
                self.dock_manager.addPerspective(name)
                persist_perspectives()
                refresh_list()
                # Select the saved item
                matches = lst.findItems(name, Qt.MatchExactly)
                if matches:
                    lst.setCurrentItem(matches[0])
            except Exception:
                QMessageBox.warning(dlg, "Save Failed", f"Could not save template '{name}'.")

        def on_delete():
            item = lst.currentItem()
            if not item:
                return
            name = item.text()
            try:
                self.dock_manager.removePerspective(name)
                persist_perspectives()
                refresh_list()
            except Exception:
                # Attempt manual removal via QSettings if ADS API not available
                try:
                    settings_obj = QSettings(self._perspective_file, QSettings.IniFormat)
                    settings_obj.beginGroup("perspectives")
                    settings_obj.remove(name)
                    settings_obj.endGroup()
                    persist_perspectives()
                    refresh_list()
                except Exception:
                    QMessageBox.warning(dlg, "Delete Failed", f"Could not delete template '{name}'.")

        btn_load.clicked.connect(on_load)
        btn_save.clicked.connect(on_save)
        btn_delete.clicked.connect(on_delete)
        btn_close.clicked.connect(dlg.accept)

        dlg.setModal(True)
        dlg.resize(420, 300)
        dlg.exec()

    def toggle_dock_lock(self, locked: bool) -> None:
        """Lock/unlock docking so docks can't be dragged or re-arranged."""
        # Preferred: global docking enable/disable on the manager
        try:
            if hasattr(self.dock_manager, "setDockingEnabled"):
                self.dock_manager.setDockingEnabled(not locked)
                return
        except Exception:
            pass

        # Fallback: adjust features on individual dock widgets if available
        for dw in self.findChildren(CDockWidget):
            try:
                # Try common API patterns
                if hasattr(dw, "setMovable"):
                    dw.setMovable(not locked)  # type: ignore[attr-defined]
                if hasattr(dw, "setFloatable"):
                    dw.setFloatable(not locked)  # type: ignore[attr-defined]
                if hasattr(dw, "setClosable"):
                    # Keep closable regardless of lock to avoid trapping users
                    pass
                # ADS specific: toggle features bitmask if present
                if hasattr(dw, "setFeatures") and hasattr(dw, "features"):
                    try:
                        feats = dw.features()
                        # Heuristic: features enum likely has these attributes
                        movable = getattr(type(feats), "DockWidgetMovable", None)
                        floatable = getattr(type(feats), "DockWidgetFloatable", None)
                        if movable is not None:
                            if locked and (feats & movable):
                                feats = feats & (~movable)
                            elif not locked and not (feats & movable):
                                feats = feats | movable
                        if floatable is not None:
                            if locked and (feats & floatable):
                                feats = feats & (~floatable)
                            elif not locked and not (feats & floatable):
                                feats = feats | floatable
                        dw.setFeatures(feats)
                    except Exception:
                        pass
            except Exception:
                pass


    def update_title_with_active_incident(self):
        """Refresh window title when active incident changes."""
        incident_number = AppState.get_active_incident()
        user_id = AppState.get_active_user_id()
        user_role = AppState.get_active_user_role()
        if incident_number:
            incident = get_incident_by_number(incident_number)
            if incident:
                suffix = ""
                if user_id or user_role:
                    suffix = f"  •  User: {user_id or ''} ({user_role or ''})"
                self.setWindowTitle(f"SARApp - {incident['number']}: {incident['name']}{suffix}")
        else:
            suffix = ""
            if user_id or user_role:
                suffix = f"  •  User: {user_id or ''} ({user_role or ''})"
            self.setWindowTitle(f"SARApp - No Incident Loaded{suffix}")

        # Also update the active incident label so it stays in sync with the title
        if hasattr(self, "update_active_incident_label"):
            self.update_active_incident_label()

        # Instrumentation
        print(
            f"[main] update_title_with_active_incident: AppState={AppState.get_active_incident()}, "
            f"self.current_incident_id={getattr(self,'current_incident_id',None)}"
        )

    def update_active_incident_label(self):
        """Update the active incident debug label with the current incident details."""
        # Determine the incident number via current_incident_id or AppState
        incident_id = getattr(self, "current_incident_id", None)
        if incident_id:
            incident = get_incident_by_number(incident_id)
        else:
            incident_number = AppState.get_active_incident()
            incident = get_incident_by_number(incident_number) if incident_number else None

        # Construct the display text based on the result
        user_id = AppState.get_active_user_id()
        user_role = AppState.get_active_user_role()
        if incident:
            text = (
                f"Incident: {incident['number']} | {incident['name']}  •  "
                f"User: {user_id or '-'}  •  Role: {user_role or '-'}"
            )
        else:
            text = f"Incident: None  •  User: {user_id or '-'}  •  Role: {user_role or '-'}"

        # Normalize no-incident text
        try:
            if 'Incident: None' in text:
                text = text.replace('Incident: None', 'Incident: No Incident Loaded', 1)
        except Exception:
            pass

        # Normalize no-incident text
        try:
            if 'Incident: None' in text:
                text = text.replace('Incident: None', 'Incident: No Incident Loaded', 1)
        except Exception:
            pass

        # Update the label if it exists (e.g. if the debug panel was created)
        if hasattr(self, "active_incident_label"):
            self.active_incident_label.setText(text)

    # --- Metric Widgets (simple counters) ---------------------------------
    def open_home_dashboard(self) -> None:
        from ui.dashboard.home_dashboard import HomeDashboard
        panel = HomeDashboard(self.settings_manager)
        # docked by default
        self._open_dock_widget(panel, title="Home Dashboard", float_on_open=False)

    def open_widget_with_id(self, widget_id: str) -> None:
        """Instantiate a registered widget by id and open it in a dock."""
        try:
            from ui.widgets import registry as W
            from ui.widgets.components import QuickEntryWidget
            from ui.actions.quick_entry_actions import dispatch as qe_dispatch, execute_cli as qe_cli
        except Exception as e:
            QMessageBox.critical(self, "Widgets", f"Widget system unavailable: {e}")
            return

        spec = W.REGISTRY.get(widget_id)
        if not spec:
            QMessageBox.warning(self, "Widgets", f"Unknown widget: {widget_id}")
            return

        # Construct component
        try:
            if widget_id == "quickEntry":
                comp = QuickEntryWidget(qe_dispatch, qe_cli)
            else:
                comp_factory = spec.component
                comp = comp_factory() if callable(comp_factory) else comp_factory  # type: ignore
                if comp is None:
                    raise RuntimeError("Widget component not available")
        except Exception as e:
            QMessageBox.critical(self, spec.title, f"Failed to render widget: {e}")
            return

        self._open_dock_widget(comp, title=spec.title, float_on_open=False)

    def _count_open_tasks(self) -> int:
        """Best-effort count of tasks not complete. Uses sample data fallback."""
        try:
            from data.sample_data import sample_tasks
            return sum(1 for t in sample_tasks if str(getattr(t, 'status', '')).lower() not in {"complete", "completed"})
        except Exception:
            try:
                from data.sample_data import TASK_ROWS, TASK_HEADERS
                si = TASK_HEADERS.index("Status") if "Status" in TASK_HEADERS else 2
                return sum(1 for row in TASK_ROWS if str(row[si]).lower() not in {"complete", "completed"})
            except Exception:
                return 0

    def _count_active_teams(self) -> int:
        """Best-effort count of teams considered active (not Out of Service)."""
        try:
            from data.sample_data import sample_teams
            return sum(1 for t in sample_teams if str(getattr(t, 'status', '')).lower() not in {"out of service", "offline"})
        except Exception:
            try:
                from data.sample_data import TEAM_ROWS, TEAM_HEADERS
                si = TEAM_HEADERS.index("Status") if "Status" in TEAM_HEADERS else 4
                return sum(1 for row in TEAM_ROWS if str(row[si]).lower() not in {"out of service", "offline"})
            except Exception:
                return 0


# Lightweight widget used by the Widgets submenu for simple metrics
class MetricWidget(QWidget):
    """Deprecated simple widget (kept to avoid breaking imports)."""
    def __init__(self, *args, **kwargs):  # pragma: no cover
        super().__init__()
        lab = QLabel("Deprecated widget. Use Home Dashboard.")
        lay = QVBoxLayout(self)
        lay.addWidget(lab)

    def _open_qml_modal(self, qml_rel_path: str, title: str) -> None:
        """Open a QML Window (as a modal dialog) and inject the catalog bridge."""
        view = QQuickView()
        view.setTitle(title)
        try:
            view.setResizeMode(QQuickView.SizeRootObjectToView)
        except Exception:
            pass

        if not hasattr(self, "_catalog_bridge"):
            self._catalog_bridge = CatalogBridge(db_path="data/master.db")

        ctx = view.rootContext()
        ctx.setContextProperty("catalogBridge", self._catalog_bridge)
        ctx.setContextProperty("teamStatuses", TEAM_STATUSES)

        base = os.path.basename(qml_rel_path)
        if base == "CannedCommEntriesWindow.qml":
            try:
                from utils.constants import TEAM_STATUSES
                ctx.setContextProperty("teamStatuses", TEAM_STATUSES)
            except Exception:
                pass

        # Inject per-window SQLite models for master catalog windows
        try:
            # Strip the full suffix "Window.qml" (10 chars) to get the base name
            name = base[:-10] if base.endswith("Window.qml") else os.path.splitext(base)[0]
            # Map window base name -> table name (validate against sqlite_master)
            table = self._resolve_master_table(name)
            print(f"[main._open_qml_modal:MetricWidget] qml='{qml_rel_path}', base='{base}', name='{name}', resolved_table='{table}'")
            if table:
                model_name = f"{name}Model"
                model = SqliteTableModel("data/master.db")
                sql = f"SELECT * FROM {table}"
                print(f"[main._open_qml_modal:MetricWidget] injecting model '{model_name}' with sql: {sql}")
                model.load_query(sql)
                ctx.setContextProperty(model_name, model)
                try:
                    print(f"[main._open_qml_modal:MetricWidget] model '{model_name}' rowCount={model.rowCount()}")
                except Exception:
                    pass
            else:
                try:
                    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "master.db")
                    con = sqlite3.connect(db_path)
                    cur = con.cursor()
                    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tbls = [r[0] for r in cur.fetchall()]
                    con.close()
                    print(f"[main._open_qml_modal:MetricWidget] no table for '{name}'. sqlite tables: {tbls}")
                except Exception as e:
                    print(f"[main._open_qml_modal:MetricWidget] failed to enumerate tables: {e}")
        except Exception as e:
            print(f"[main] model injection error for {qml_rel_path}: {e}")

        from pathlib import Path
        qml_file = Path(__file__).resolve().parent / qml_rel_path
        view.setSource(QUrl.fromLocalFile(str(qml_file)))
        view.show()
        if not hasattr(self, "_open_qml_views"):
            self._open_qml_views = []
        self._open_qml_views.append(view)

    def _open_qml_placeholder(self, title: str, body: str, float_on_open: bool = True) -> None:
        qml_file = os.path.join("ui", "qml", "PlaceholderPanel.qml")
        ctx = {"panelTitle": title, "panelBody": body}
        self._open_dock_from_qml(qml_file, title, float_on_open=float_on_open, context=ctx)

    # (Deprecated widget openers removed in favor of Home Dashboard)

    def _count_open_tasks(self) -> int:
        """Best-effort count of tasks not complete. Uses sample data fallback."""
        try:
            from data.sample_data import sample_tasks
            return sum(1 for t in sample_tasks if str(getattr(t, 'status', '')).lower() not in {"complete", "completed"})
        except Exception:
            try:
                from data.sample_data import TASK_ROWS, TASK_HEADERS
                si = TASK_HEADERS.index("Status") if "Status" in TASK_HEADERS else 2
                return sum(1 for row in TASK_ROWS if str(row[si]).lower() not in {"complete", "completed"})
            except Exception:
                return 0

    def _count_active_teams(self) -> int:
        """Best-effort count of teams considered active (not Out of Service)."""
        try:
            from data.sample_data import sample_teams
            return sum(1 for t in sample_teams if str(getattr(t, 'status', '')).lower() not in {"out of service", "offline"})
        except Exception:
            try:
                from data.sample_data import TEAM_ROWS, TEAM_HEADERS
                si = TEAM_HEADERS.index("Status") if "Status" in TEAM_HEADERS else 4
                return sum(1 for row in TEAM_ROWS if str(row[si]).lower() not in {"out of service", "offline"})
            except Exception:
                return 0

    def _resolve_master_table(self, base_name: str) -> str | None:
        """Resolve a master.db table name for a given Window base name.
        Uses sqlite_master to confirm existence and tries sensible mappings,
        including canonical names from master_catalog where applicable.
        """
        # List all tables from master.db
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "master.db")
        tables: set[str] = set()
        try:
            con = sqlite3.connect(db_path)
            cur = con.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {r[0] for r in cur.fetchall()}
            con.close()
        except Exception as e:
            print(f"[main] _resolve_master_table: unable to read tables: {e}")
            return None

        # Canonical known mappings
        canonical = {
            "Personnel": "personnel",
            "Vehicles": "vehicles",
            "Aircraft": "aircraft",
            "Equipment": "equipment",
            "CommsResources": "comms_resources",
            "Objectives": "incident_objectives",
            "Certifications": "certification_types",
            "TeamTypes": "team_types",
            "TaskTypes": "task_types",
            "CannedCommEntries": "canned_comm_entries",
            "Ems": "ems",
            "Hospitals": "ems",  # window displays EMS-style contacts
            "SafetyTemplates": "safety_templates",
        }

        # 1) Try canonical mapping
        tbl = canonical.get(base_name)
        if tbl and tbl in tables:
            return tbl

        # 2) Try snake_case of base name
        import re
        snake = re.sub(r"(?<!^)([A-Z])", r"_\1", base_name).lower()
        if snake in tables:
            return snake

        # 3) Try simple lowercase/plural checks
        low = base_name.lower()
        if low in tables:
            return low
        if f"{low}s" in tables:
            return f"{low}s"

        # 4) Nothing matched
        return None


    def update_title_with_active_incident(self):
        """Refresh window title when active incident changes."""
        incident_number = AppState.get_active_incident()
        user_id = AppState.get_active_user_id()
        user_role = AppState.get_active_user_role()
        if incident_number:
            incident = get_incident_by_number(incident_number)
            if incident:
                suffix = ""
                if user_id or user_role:
                    suffix = f" — User: {user_id or ''} ({user_role or ''})"
                self.setWindowTitle(f"SARApp - {incident['number']}: {incident['name']}{suffix}")
        else:
            suffix = ""
            if user_id or user_role:
                suffix = f" — User: {user_id or ''} ({user_role or ''})"
            self.setWindowTitle(f"SARApp - No Incident Loaded{suffix}")

        # Also update the active incident label so it stays in sync with the title
        # (this will only have an effect if the debug panel has been created)
        if hasattr(self, "update_active_incident_label"):
            self.update_active_incident_label()

        # Instrumentation
        print(f"[main] update_title_with_active_incident: AppState={AppState.get_active_incident()}, self.current_incident_id={getattr(self,'current_incident_id',None)}")

    def update_active_incident_label(self):
        """
        Update the active incident debug label with the current incident details.

        If the main window has a current_incident_id attribute, use it to look up
        the incident; otherwise fall back to whatever AppState reports as the
        active incident. The label will show the incident number and name if
        available, or indicate that no incident is active.
        """
        # Determine the incident number via current_incident_id or AppState
        incident_id = getattr(self, "current_incident_id", None)
        if incident_id:
            incident = get_incident_by_number(incident_id)
        else:
            incident_number = AppState.get_active_incident()
            incident = get_incident_by_number(incident_number) if incident_number else None

        # Construct the display text based on the result
        user_id = AppState.get_active_user_id()
        user_role = AppState.get_active_user_role()
        if incident:
            text = f"Incident: {incident['number']} | {incident['name']}  •  User: {user_id or '-'}  •  Role: {user_role or '-'}"
        else:
            text = f"Incident: None  •  User: {user_id or '-'}  •  Role: {user_role or '-'}"

        # Update the label if it exists (e.g. if the debug panel was created)
        if hasattr(self, "active_incident_label"):
            self.active_incident_label.setText(text)


# ===== Part 6: Application Entrypoint =======================================
if __name__ == "__main__":
    import argparse
    app = QApplication(sys.argv)
    apply_app_palette(app)

    def _on_quit():
        try:
            sid = AppState.get_active_session_id()
            if sid is not None:
                end_session()
                write_audit("session.end", {"session_id": sid}, prefer_mission=False)
        except Exception:
            pass
    app.aboutToQuit.connect(_on_quit)

    # ==== DEBUG LOGIN BYPASS (set to True to skip login) ====
    DEBUG_BYPASS_LOGIN = True  # <--- Toggle this to True to skip login dialog
    DEBUG_INCIDENT_ID = "2025-FAIR"
    DEBUG_USER_ID = "405021"
    DEBUG_ROLE = "Incident Commander"
    # =========================================================

    # Optional demo mode: relax validation on the login dialog
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--demo", action="store_true", help="Start in demo mode (relaxed login validation)")
    try:
        args, _ = parser.parse_known_args()
    except SystemExit:
        class _Args: demo = False
        args = _Args()

    if DEBUG_BYPASS_LOGIN:
        # Insert your session management or state setup here
        # For example:
        from utils import state
        AppState.set_active_incident(DEBUG_INCIDENT_ID)
        AppState.set_active_user_id(DEBUG_USER_ID)
        AppState.set_active_user_role(DEBUG_ROLE)
        print("[debug] Login bypass enabled: loaded test credentials.")
    else:
        from modules.login_dialog import LoginDialog
        login = LoginDialog(demo_mode=bool(getattr(args, "demo", False)))
        if login.exec() != QDialog.Accepted:
            sys.exit(0)

    # Build main window after session is established
    settings_manager = SettingsManager()
    settings_bridge = QmlSettingsBridge(settings_manager)

    win = MainWindow(settings_manager=settings_manager, settings_bridge=settings_bridge)
    win.show()
    sys.exit(app.exec())


