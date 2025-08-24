# ===== Part 1: Imports & Logging ============================================
import sys
import logging
from typing import Callable
from xml.sax import handler  # preserved from original

from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QPushButton,
    QMainWindow,
    QMenu,
    QLabel,
    QWidget,
    QVBoxLayout,
)
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtCore import Qt, QUrl
from PySide6.QtQuick import QQuickView

# (Panels previously used directly; retained imports in case you still need them elsewhere)
from modules.operations.panels.team_status_panel import TeamStatusPanel
from modules.operations.panels.task_status_panel import TaskStatusPanel

# (QML utilities kept, though handlers now follow panel-factory pattern)
from models.qmlwindow import QmlWindow, new_mission_form, open_mission_list
from utils.state import AppState
from models.database import get_mission_by_number
from bridge.settings_bridge import QmlSettingsBridge
from utils.settingsmanager import SettingsManager

logger = logging.getLogger(__name__)


# ===== Part 2: Main Window & Physical Menus (visible UI only) ===============
class MainWindow(QMainWindow):
    """
    Menu-first structure. Every visible menu item has a corresponding handler method,
    and ALL handlers follow the same pattern:
      - import module
      - mission_id = getattr(self, "current_mission_id", None)
      - panel = module.get_*_panel(mission_id)
      - self._open_modeless(panel, title="...")
    Placeholders are fine if a real module/factory doesn't exist yet.
    """
    def __init__(self, settings_manager: SettingsManager | None = None,
                 settings_bridge: QmlSettingsBridge | None = None):
        super().__init__()
        self.setStyleSheet("background-color: #f5f5f5;")
        self._open_windows: list[QWidget] = []  # track modeless windows

        if settings_manager is None:
            settings_manager = SettingsManager()
        if settings_bridge is None:
            settings_bridge = QmlSettingsBridge(settings_manager)
        self.settings_manager = settings_manager
        self.settings_bridge = settings_bridge

        # Title includes active mission (if any)
        active_number = AppState.get_active_mission()
        if active_number:
            mission = get_mission_by_number(active_number)
            if mission:
                title = f"SARApp - {mission['number']} | {mission['name']}"
            else:
                title = "SARApp - Incident Management Assistant"
        else:
            title = "SARApp - Incident Management Assistant"
        self.setWindowTitle(title)
        self.resize(1280, 800)

        # Central placeholder
        self.setCentralWidget(QLabel("SARApp Dashboard"))

        # Example dock panels
        dock = QDockWidget("Teams Panel", self)
        dock.setWidget(QPushButton("Open Task Detail"))
        dock.widget().clicked.connect(self.open_task_detail)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

        team_panel = TeamStatusPanel()
        dock = QDockWidget("Team Status", self)
        dock.setWidget(team_panel)
        self.addDockWidget(Qt.TopDockWidgetArea, dock)

        task_panel = TaskStatusPanel()
        dock = QDockWidget("Task Status", self)
        dock.setWidget(task_panel)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)

        # Build the physical menu bar (visible UI)
        self.init_module_menus()

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
        self._add_action(m_menu, "New Mission", "Ctrl+N", "menu.new_mission")
        self._add_action(m_menu, "Open Mission", "Ctrl+O", "menu.open_mission")
        self._add_action(m_menu, "Save Mission", "Ctrl+S", "menu.save_mission")
        self._add_action(m_menu, "Settings", None, "menu.settings")
        m_menu.addSeparator()
        self._add_action(m_menu, "Exit", "Ctrl+Q", "menu.exit")

        # ----- Edit -----
        m_edit = mb.addMenu("Edit")
        self._add_action(m_edit, "EMS and Hospitals", None, "edit.ems_hospitals")
        self._add_action(m_edit, "Canned Communication Entries", None, "edit.canned_comm_entries")
        self._add_action(m_edit, "Personnel", None, "edit.personnel")
        self._add_action(m_edit, "Objectives", None, "edit.objectives")
        self._add_action(m_edit, "Task Types", None, "edit.task_types")
        self._add_action(m_edit, "Team Types", None, "edit.team_types")
        self._add_action(m_edit, "Vehicles", None, "edit.vehicles")
        self._add_action(m_edit, "Equipment", None, "edit.equipment")
        self._add_action(m_edit, "Communications Resources", None, "communications.217")

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
        m_med = mb.addMenu("Medical & Safety")
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
        self._add_action(m_fin, "Expenses & Procurement", None, "finance.procurement")
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
        self._add_action(plan_menu, "Vendors & Permits", None, "planned.vendors")
        self._add_action(plan_menu, "Public Safety", None, "planned.safety")
        self._add_action(plan_menu, "Tasking & Assignments", None, "planned.tasking")
        self._add_action(plan_menu, "Health & Sanitation", None, "planned.health_sanitation")

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
        handlers: dict[str, Callable[[], None]] = {
            # ----- Menu -----
            "menu.new_mission": self.open_menu_new_mission,
            "menu.open_mission": self.open_menu_open_mission,
            "menu.save_mission": self.open_menu_save_mission,
            "menu.settings": self.open_menu_settings,
            "menu.exit": self.open_menu_exit,  # special-case: still exits

            # ----- Edit -----
            "edit.ems_hospitals": self.open_edit_ems_hospitals,
            "edit.canned_comm_entries": self.open_edit_canned_comm_entries,
            "edit.personnel": self.open_edit_personnel,
            "edit.objectives": self.open_edit_objectives,
            "edit.task_types": self.open_edit_task_types,
            "edit.team_types": self.open_edit_team_types,
            "edit.vehicles": self.open_edit_vehicles,
            "edit.equipment": self.open_edit_equipment,
            "communications.217": self.open_edit_comms_resources,

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
        }

        handler = handlers.get(key)
        if handler:
            handler()
        else:
            print(f"[OpenModule] no handler for {key}")

# ===== Part 4: Handlers in Menu Order (panel-factory pattern) ============
# --- 4.1 Menu ------------------------------------------------------------
    def open_menu_new_mission(self) -> None:
        from modules import missions
        mission_id = getattr(self, "current_mission_id", None)
        panel = missions.get_new_mission_panel(mission_id)
        self._open_modeless(panel, title="New Mission")

    def open_menu_open_mission(self) -> None:
        from modules import missions
        mission_id = getattr(self, "current_mission_id", None)
        panel = missions.get_mission_list_panel(mission_id)
        self._open_modeless(panel, title="Open Mission")

    def open_menu_save_mission(self) -> None:
        from modules import missions
        mission_id = getattr(self, "current_mission_id", None)
        panel = missions.get_save_mission_panel(mission_id)
        self._open_modeless(panel, title="Save Mission")

    def open_menu_settings(self) -> None:
        from modules import settingsui
        mission_id = getattr(self, "current_mission_id", None)
        panel = settingsui.get_settings_panel(mission_id)
        self._open_modeless(panel, title="Settings")

    def open_menu_exit(self) -> None:
        # Exit remains a direct action rather than opening a panel.
        QApplication.instance().quit()

# --- 4.2 Edit ------------------------------------------------------------
    def open_edit_ems_hospitals(self) -> None:
        from modules import editpanels
        mission_id = getattr(self, "current_mission_id", None)
        panel = editpanels.get_ems_hospitals_panel(mission_id)
        self._open_modeless(panel, title="EMS & Hospitals")

    def open_edit_canned_comm_entries(self) -> None:
        from modules import editpanels
        mission_id = getattr(self, "current_mission_id", None)
        panel = editpanels.get_canned_comm_entries_panel(mission_id)
        self._open_modeless(panel, title="Canned Communication Entries")

    def open_edit_personnel(self) -> None:
        from modules import logistics
        mission_id = getattr(self, "current_mission_id", None)
        panel = logistics.get_personnel_panel(mission_id)
        self._open_modeless(panel, title="Personnel")

    def open_edit_objectives(self) -> None:
        from modules import editpanels
        mission_id = getattr(self, "current_mission_id", None)
        panel = editpanels.get_objectives_panel(mission_id)
        self._open_modeless(panel, title="Objectives")

    def open_edit_task_types(self) -> None:
        from modules import editpanels
        mission_id = getattr(self, "current_mission_id", None)
        panel = editpanels.get_task_types_panel(mission_id)
        self._open_modeless(panel, title="Task Types")

    def open_edit_team_types(self) -> None:
        from modules import editpanels
        mission_id = getattr(self, "current_mission_id", None)
        panel = editpanels.get_team_types_panel(mission_id)
        self._open_modeless(panel, title="Team Types")

    def open_edit_vehicles(self) -> None:
        from modules import logistics
        mission_id = getattr(self, "current_mission_id", None)
        panel = logistics.get_vehicles_panel(mission_id)
        self._open_modeless(panel, title="Vehicles")

    def open_edit_equipment(self) -> None:
        from modules import logistics
        mission_id = getattr(self, "current_mission_id", None)
        panel = logistics.get_equipment_panel(mission_id)
        self._open_modeless(panel, title="Equipment")

    def open_edit_comms_resources(self) -> None:
        from modules import comms
        mission_id = getattr(self, "current_mission_id", None)
        panel = comms.get_217_panel(mission_id)
        self._open_modeless(panel, title="Communications Resources (ICS-217)")

# --- 4.3 Command ---------------------------------------------------------
    def open_command_unit_log(self) -> None:
        from modules import ics214
        mission_id = getattr(self, "current_mission_id", None)
        panel = ics214.get_ics214_panel(mission_id)
        self._open_modeless(panel, title="ICS-214 Activity Log")

    def open_command_incident_overview(self) -> None:
        from modules import command
        mission_id = getattr(self, "current_mission_id", None)
        panel = command.get_incident_overview_panel(mission_id)
        self._open_modeless(panel, title="Incident Overview")

    def open_command_iap(self) -> None:
        from modules import command
        mission_id = getattr(self, "current_mission_id", None)
        panel = command.get_iap_builder_panel(mission_id)
        self._open_modeless(panel, title="Incident Action Plan Builder")

    def open_command_objectives(self) -> None:
        from modules import command
        mission_id = getattr(self, "current_mission_id", None)
        panel = command.get_objectives_panel(mission_id)
        self._open_modeless(panel, title="Incident Objectives (ICS 202)")

    def open_command_staff_org(self) -> None:
        from modules import command
        mission_id = getattr(self, "current_mission_id", None)
        panel = command.get_staff_org_panel(mission_id)
        self._open_modeless(panel, title="Command Staff Organization (ICS 203)")

    def open_command_sitrep(self) -> None:
        from modules import command
        mission_id = getattr(self, "current_mission_id", None)
        panel = command.get_sitrep_panel(mission_id)
        self._open_modeless(panel, title="Situation Report (ICS 209)")

# --- 4.4 Planning --------------------------------------------------------
    def open_planning_unit_log(self) -> None:
        from modules import ics214
        mission_id = getattr(self, "current_mission_id", None)
        panel = ics214.get_ics214_panel(mission_id)
        self._open_modeless(panel, title="ICS-214 Activity Log")

    def open_planning_dashboard(self) -> None:
        from modules import planning
        mission_id = getattr(self, "current_mission_id", None)
        panel = planning.get_dashboard_panel(mission_id)
        self._open_modeless(panel, title="Planning Dashboard")

    def open_planning_approvals(self) -> None:
        from modules import planning
        mission_id = getattr(self, "current_mission_id", None)
        panel = planning.get_approvals_panel(mission_id)
        self._open_modeless(panel, title="Pending Approvals")

    def open_planning_forecast(self) -> None:
        from modules import planning
        mission_id = getattr(self, "current_mission_id", None)
        panel = planning.get_forecast_panel(mission_id)
        self._open_modeless(panel, title="Planning Forecast")

    def open_planning_op_manager(self) -> None:
        from modules import planning
        mission_id = getattr(self, "current_mission_id", None)
        panel = planning.get_op_manager_panel(mission_id)
        self._open_modeless(panel, title="Operational Period Manager")

    def open_planning_taskmetrics(self) -> None:
        from modules import planning
        mission_id = getattr(self, "current_mission_id", None)
        panel = planning.get_taskmetrics_panel(mission_id)
        self._open_modeless(panel, title="Task Metrics Dashboard")

    def open_planning_strategic_objectives(self) -> None:
        from modules import planning
        mission_id = getattr(self, "current_mission_id", None)
        panel = planning.get_strategic_objectives_panel(mission_id)
        self._open_modeless(panel, title="Strategic Objective Tracker")

    def open_planning_sitrep(self) -> None:
        from modules import planning
        mission_id = getattr(self, "current_mission_id", None)
        panel = planning.get_sitrep_panel(mission_id)
        self._open_modeless(panel, title="Situation Report")

# --- 4.5 Operations ------------------------------------------------------
    def open_operations_unit_log(self) -> None:
        from modules import ics214
        mission_id = getattr(self, "current_mission_id", None)
        panel = ics214.get_ics214_panel(mission_id)
        self._open_modeless(panel, title="ICS-214 Activity Log")

    def open_operations_dashboard(self) -> None:
        from modules import operations
        mission_id = getattr(self, "current_mission_id", None)
        panel = operations.get_dashboard_panel(mission_id)
        self._open_modeless(panel, title="Assignments Dashboard")

    def open_operations_team_assignments(self) -> None:
        from modules import operations
        mission_id = getattr(self, "current_mission_id", None)
        panel = operations.get_team_assignments_panel(mission_id)
        self._open_modeless(panel, title="Team Assignments")

# --- 4.6 Logistics -------------------------------------------------------
    def open_logistics_unit_log(self) -> None:
        from modules import ics214
        mission_id = getattr(self, "current_mission_id", None)
        panel = ics214.get_ics214_panel(mission_id)
        self._open_modeless(panel, title="ICS-214 Activity Log")

    def open_logistics_dashboard(self) -> None:
        from modules import logistics
        mission_id = getattr(self, "current_mission_id", None)
        panel = logistics.get_logistics_panel(mission_id)
        self._open_modeless(panel, title="Logistics Dashboard")

    def open_logistics_211(self) -> None:
        from modules import logistics
        mission_id = getattr(self, "current_mission_id", None)
        panel = logistics.get_checkin_panel(mission_id)
        self._open_modeless(panel, title="Check-In (ICS-211)")

    def open_logistics_requests(self) -> None:
        from modules import logistics
        mission_id = getattr(self, "current_mission_id", None)
        panel = logistics.get_requests_panel(mission_id)
        self._open_modeless(panel, title="Resource Requests")

    def open_logistics_equipment(self) -> None:
        from modules import logistics
        mission_id = getattr(self, "current_mission_id", None)
        panel = logistics.get_equipment_panel(mission_id)
        self._open_modeless(panel, title="Equipment Inventory")

    def open_logistics_213rr(self) -> None:
        from modules import logistics
        mission_id = getattr(self, "current_mission_id", None)
        panel = logistics.get_213rr_panel(mission_id)
        self._open_modeless(panel, title="Resource Request (ICS-213RR)")

# --- 4.7 Communications --------------------------------------------------
    def open_comms_unit_log(self) -> None:
        from modules import ics214
        mission_id = getattr(self, "current_mission_id", None)
        panel = ics214.get_ics214_panel(mission_id)
        self._open_modeless(panel, title="ICS-214 Activity Log")

    def open_comms_chat(self) -> None:
        from modules import comms
        mission_id = getattr(self, "current_mission_id", None)
        panel = comms.get_chat_panel(mission_id)
        self._open_modeless(panel, title="Messaging")

    def open_comms_213(self) -> None:
        from modules import comms
        mission_id = getattr(self, "current_mission_id", None)
        panel = comms.get_213_panel(mission_id)
        self._open_modeless(panel, title="ICS 213 Messages")

    def open_comms_205(self) -> None:
        from modules import comms
        mission_id = getattr(self, "current_mission_id", None)
        panel = comms.get_205_panel(mission_id)
        self._open_modeless(panel, title="Communications Plan (ICS-205)")

# --- 4.8 Intel -----------------------------------------------------------
    def open_intel_unit_log(self) -> None:
        from modules import ics214
        mission_id = getattr(self, "current_mission_id", None)
        panel = ics214.get_ics214_panel(mission_id)
        self._open_modeless(panel, title="ICS-214 Activity Log")

    def open_intel_dashboard(self) -> None:
        from modules import intel
        mission_id = getattr(self, "current_mission_id", None)
        panel = intel.get_dashboard_panel(mission_id)
        self._open_modeless(panel, title="Intel Dashboard")

    def open_intel_clue_log(self) -> None:
        from modules import intel
        mission_id = getattr(self, "current_mission_id", None)
        panel = intel.get_clue_log_panel(mission_id)
        self._open_modeless(panel, title="Clue Log (SAR-134)")

    def open_intel_add_clue(self) -> None:
        from modules import intel
        mission_id = getattr(self, "current_mission_id", None)
        panel = intel.get_add_clue_panel(mission_id)
        self._open_modeless(panel, title="Add Clue (SAR-135)")

# --- 4.9 Medical & Safety -----------------------------------------------
    def open_medical_unit_log(self) -> None:
        from modules import ics214
        mission_id = getattr(self, "current_mission_id", None)
        panel = ics214.get_ics214_panel(mission_id)
        self._open_modeless(panel, title="ICS-214 Activity Log")

    def open_safety_unit_log(self) -> None:
        from modules import ics214
        mission_id = getattr(self, "current_mission_id", None)
        panel = ics214.get_ics214_panel(mission_id)
        self._open_modeless(panel, title="ICS-214 Activity Log")

    def open_medical_206(self) -> None:
        from modules import medical
        mission_id = getattr(self, "current_mission_id", None)
        panel = medical.get_206_panel(mission_id)
        self._open_modeless(panel, title="Medical Plan (ICS 206)")

    def open_safety_208(self) -> None:
        from modules import safety
        mission_id = getattr(self, "current_mission_id", None)
        panel = safety.get_208_panel(mission_id)
        self._open_modeless(panel, title="Safety Message (ICS-208)")

    def open_safety_215A(self) -> None:
        from modules import safety
        mission_id = getattr(self, "current_mission_id", None)
        panel = safety.get_215A_panel(mission_id)
        self._open_modeless(panel, title="Incident Safety Analysis (ICS-215A)")

    def open_safety_caporm(self) -> None:
        from modules import safety
        mission_id = getattr(self, "current_mission_id", None)
        panel = safety.get_caporm_panel(mission_id)
        self._open_modeless(panel, title="CAP ORM")

# --- 4.10 Liaison --------------------------------------------------------
    def open_liaison_unit_log(self) -> None:
        from modules import ics214
        mission_id = getattr(self, "current_mission_id", None)
        panel = ics214.get_ics214_panel(mission_id)
        self._open_modeless(panel, title="ICS-214 Activity Log")

    def open_liaison_agencies(self) -> None:
        from modules import liaison
        mission_id = getattr(self, "current_mission_id", None)
        panel = liaison.get_agencies_panel(mission_id)
        self._open_modeless(panel, title="Agency Directory")

    def open_liaison_requests(self) -> None:
        from modules import liaison
        mission_id = getattr(self, "current_mission_id", None)
        panel = liaison.get_requests_panel(mission_id)
        self._open_modeless(panel, title="Customer Requests")

# --- 4.11 Public Information --------------------------------------------
    def open_public_unit_log(self) -> None:
        from modules import ics214
        mission_id = getattr(self, "current_mission_id", None)
        panel = ics214.get_ics214_panel(mission_id)
        self._open_modeless(panel, title="ICS-214 Activity Log")

    def open_public_media_releases(self) -> None:
        from modules import public_info
        mission_id = getattr(self, "current_mission_id", None)
        panel = public_info.get_media_releases_panel(mission_id)
        self._open_modeless(panel, title="Media Releases")

    def open_public_inquiries(self) -> None:
        from modules import public_info
        mission_id = getattr(self, "current_mission_id", None)
        panel = public_info.get_inquiries_panel(mission_id)
        self._open_modeless(panel, title="Public Inquiries")

# --- 4.12 Finance/Admin --------------------------------------------------
    def open_finance_unit_log(self) -> None:
        from modules import ics214
        mission_id = getattr(self, "current_mission_id", None)
        panel = ics214.get_ics214_panel(mission_id)
        self._open_modeless(panel, title="ICS-214 Activity Log")

    def open_finance_time(self) -> None:
        from modules import finance
        mission_id = getattr(self, "current_mission_id", None)
        panel = finance.get_time_panel(mission_id)
        self._open_modeless(panel, title="Time Tracking")

    def open_finance_procurement(self) -> None:
        from modules import finance
        mission_id = getattr(self, "current_mission_id", None)
        panel = finance.get_procurement_panel(mission_id)
        self._open_modeless(panel, title="Expenses & Procurement")

    def open_finance_summary(self) -> None:
        from modules import finance
        mission_id = getattr(self, "current_mission_id", None)
        panel = finance.get_summary_panel(mission_id)
        self._open_modeless(panel, title="Cost Summary")

# --- 4.13 Toolkits -------------------------------------------------------
    def open_toolkit_sar_missing_person(self) -> None:
        from modules.sartoolkit import sar
        mission_id = getattr(self, "current_mission_id", None)
        panel = sar.get_missing_person_panel(mission_id)
        self._open_modeless(panel, title="Missing Person Toolkit")

    def open_toolkit_sar_pod(self) -> None:
        from modules.sartoolkit import sar
        mission_id = getattr(self, "current_mission_id", None)
        panel = sar.get_pod_panel(mission_id)
        self._open_modeless(panel, title="POD Calculator")

    def open_toolkit_disaster_damage(self) -> None:
        from modules.disasterresponse import disaster
        mission_id = getattr(self, "current_mission_id", None)
        panel = disaster.get_damage_panel(mission_id)
        self._open_modeless(panel, title="Damage Assessment")

    def open_toolkit_disaster_urban_interview(self) -> None:
        from modules.disasterresponse import disaster
        mission_id = getattr(self, "current_mission_id", None)
        panel = disaster.get_urban_interview_panel(mission_id)
        self._open_modeless(panel, title="Urban Interview Log")

    def open_toolkit_disaster_photos(self) -> None:
        from modules.disasterresponse import disaster
        mission_id = getattr(self, "current_mission_id", None)
        panel = disaster.get_photos_panel(mission_id)
        self._open_modeless(panel, title="Damage Photos")

    def open_planned_promotions(self) -> None:
        from modules import plannedtoolkit
        mission_id = getattr(self, "current_mission_id", None)
        panel = plannedtoolkit.get_promotions_panel(mission_id)
        self._open_modeless(panel, title="External Messaging")

    def open_planned_vendors(self) -> None:
        from modules import plannedtoolkit
        mission_id = getattr(self, "current_mission_id", None)
        panel = plannedtoolkit.get_vendors_panel(mission_id)
        self._open_modeless(panel, title="Vendors & Permits")

    def open_planned_safety(self) -> None:
        from modules import plannedtoolkit
        mission_id = getattr(self, "current_mission_id", None)
        panel = plannedtoolkit.get_safety_panel(mission_id)
        self._open_modeless(panel, title="Public Safety")

    def open_planned_tasking(self) -> None:
        from modules import plannedtoolkit
        mission_id = getattr(self, "current_mission_id", None)
        panel = plannedtoolkit.get_tasking_panel(mission_id)
        self._open_modeless(panel, title="Tasking & Assignments")

    def open_planned_health_sanitation(self) -> None:
        from modules import plannedtoolkit
        mission_id = getattr(self, "current_mission_id", None)
        panel = plannedtoolkit.get_health_sanitation_panel(mission_id)
        self._open_modeless(panel, title="Health & Sanitation")

    def open_toolkit_initial_hasty(self) -> None:
        from modules.initalresponse import initial
        mission_id = getattr(self, "current_mission_id", None)
        panel = initial.get_hasty_panel(mission_id)
        self._open_modeless(panel, title="Hasty Tools")

    def open_toolkit_initial_reflex(self) -> None:
        from modules.initalresponse import initial
        mission_id = getattr(self, "current_mission_id", None)
        panel = initial.get_reflex_panel(mission_id)
        self._open_modeless(panel, title="Reflex Taskings")

# --- 4.14 Resources (Forms & Library) -----------------------------------
    def open_forms(self) -> None:
        from modules import referencelibrary
        mission_id = getattr(self, "current_mission_id", None)
        panel = referencelibrary.get_form_library_panel(mission_id)
        self._open_modeless(panel, title="Form Library")

    def open_reference_library(self) -> None:
        from modules import referencelibrary
        mission_id = getattr(self, "current_mission_id", None)
        panel = referencelibrary.get_library_panel()
        self._open_modeless(panel, title="Reference Library")

    def open_help_user_guide(self) -> None:
        from modules import helpdocs
        mission_id = getattr(self, "current_mission_id", None)
        panel = helpdocs.get_user_guide_panel(mission_id)
        self._open_modeless(panel, title="User Guide")

# --- 4.15 Help -----------------------------------------------------------
    def open_help_about(self) -> None:
        from modules import helpdocs
        mission_id = getattr(self, "current_mission_id", None)
        panel = helpdocs.get_about_panel(mission_id)
        self._open_modeless(panel, title="About SARApp")

# ===== Part 5: Shared Windows, Helpers & Utilities =======================
    def _open_modeless(self, widget: QWidget, title: str) -> None:
        """Display *widget* as a modeless window, tracking it for cleanup."""
        if hasattr(self, "docking_helper") and callable(
            getattr(self.docking_helper, "open_widget", None)
        ):
            self.docking_helper.open_widget(widget, title)
            return
        if hasattr(self, "mdi_area"):
            widget.setWindowTitle(title)
            self.mdi_area.addSubWindow(widget)
            widget.show()
            return

        widget.setWindowTitle(title)
        self._open_windows.append(widget)

        def _cleanup(_: object = None, w: QWidget = widget) -> None:
            if w in self._open_windows:
                self._open_windows.remove(w)

        widget.destroyed.connect(_cleanup)
        widget.show()

    def _open_docked(self, widget, title: str,
                     area=Qt.RightDockWidgetArea,
                     object_name: str | None = None) -> None:
        """Show *widget* in a QDockWidget. Reuse the dock if it already exists."""
        obj_name = object_name or f"dock::{title}"
        existing = self.findChild(QDockWidget, obj_name)
        if existing:
            old = existing.widget()
            if old is not widget:
                existing.setWidget(widget)
            existing.setWindowTitle(title)
            existing.raise_()
            existing.show()
            return

        dock = QDockWidget(title, self)
        dock.setObjectName(obj_name)
        dock.setFeatures(QDockWidget.DockWidgetMovable |
                         QDockWidget.DockWidgetFloatable |
                         QDockWidget.DockWidgetClosable)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea |
                             Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        dock.show()

    def open_task_detail(self):
        """Example QML task detail window launcher (kept for reference)."""
        self.task_window = QQuickView()
        self.task_window.setSource(QUrl("modules/operations/qml/taskdetail.qml"))
        self.task_window.setResizeMode(QQuickView.SizeRootObjectToView)
        self.task_window.setColor("white")
        self.task_window.show()

    def update_title_with_active_mission(self):
        """Refresh window title when active mission changes."""
        mission_number = AppState.get_active_mission()
        if mission_number:
            mission = get_mission_by_number(mission_number)
            if mission:
                self.setWindowTitle(f"SARApp - {mission['number']}: {mission['name']}")
        else:
            self.setWindowTitle("SARApp - Incident Management Assistant")


# ===== Part 6: Application Entrypoint =======================================
if __name__ == "__main__":
    app = QApplication(sys.argv)

    settings_manager = SettingsManager()
    settings_bridge = QmlSettingsBridge(settings_manager)

    win = MainWindow(settings_manager=settings_manager, settings_bridge=settings_bridge)
    win.show()
    sys.exit(app.exec())
