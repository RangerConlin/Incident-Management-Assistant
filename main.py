# main.py
import sys
import logging
from typing import Callable, Any, Dict
from xml.sax import handler

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
from modules.operations.panels.team_status_panel import TeamStatusPanel
from modules.operations.panels.task_status_panel import TaskStatusPanel
from models.qmlwindow import QmlWindow, new_mission_form, open_mission_list
from utils.state import AppState
from models.database import get_mission_by_number
from bridge.settings_bridge import QmlSettingsBridge
from utils.settingsmanager import SettingsManager


logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self, settings_manager: SettingsManager | None = None,
                 settings_bridge: QmlSettingsBridge | None = None):
        super().__init__()
        self.setStyleSheet("background-color: #f5f5f5;")

        # Track any modeless windows opened directly by this window
        self._open_windows: list[QWidget] = []

        if settings_manager is None:
            settings_manager = SettingsManager()
        if settings_bridge is None:
            settings_bridge = QmlSettingsBridge(settings_manager)

        self.settings_manager = settings_manager
        self.settings_bridge = settings_bridge

        # Try to load the active mission and include it in the title
        active_number = AppState.get_active_mission()
        if active_number:
            mission = get_mission_by_number(active_number)
            if mission:
                # Use an f-string so the mission details appear in the title
                title = f"SARApp - {mission['number']} | {mission['name']}"
            else:
                title = "SARApp - Incident Management Assistant"
        else:
            title = "SARApp - Incident Management Assistant"

        self.setWindowTitle(title)
        self.resize(1280, 800)

        self.setCentralWidget(QLabel("SARApp Dashboard"))

        # Dock panel example
        dock = QDockWidget("Teams Panel", self)
        dock.setWidget(QPushButton("Open Task Detail"))
        dock.widget().clicked.connect(self.open_task_detail)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

        # Team Status Dock
        team_panel = TeamStatusPanel()
        dock = QDockWidget("Team Status", self)
        dock.setWidget(team_panel)
        self.addDockWidget(Qt.TopDockWidgetArea, dock)

        # Task Status Dock
        task_panel = TaskStatusPanel()
        dock = QDockWidget("Task Status", self)
        dock.setWidget(task_panel)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)

        # Set up the full menu bar
        #self.init_menu_bar()
        self.init_module_menus()

        # Bind menu actions to their handlers when available
        self._bind_action(["actionLogistics", "Logistics"], self.open_logistics)
        self._bind_action([
            "actionSafety",
            "Safety",
            "Medical & Safety",
        ], self.open_safety)
        self._bind_action(
            ["actionReferenceLibrary", "Reference Library", "Resource Library"],
            self.open_reference_library,
        )
        self._bind_action(
            ["actionPlannedToolkit", "Planned Event Toolkit", "Planned Events"],
            self.open_planned_toolkit,
        )
        self._bind_action(["actionFinance", "Finance", "Finance/Admin"], self.open_finance)
        self._bind_action(
            ["actionPublicInfo", "Public Information", "PIO"],
            self.open_public_info,
        )

    def open_ics214(self):
            win = QmlWindow("modules/intel/qml/intellog.qml", "Intel Unit Log (ICS-214)")
            win.exec()

    def open_clue_log(self):
            win = QmlWindow("modules/intel/qml/sar134.qml", "Clue Log (SAR-134)")
            win.exec()

    def open_add_clue(self):
            win = QmlWindow("modules/intel/qml/sar135.qml", "Add Clue (SAR-135)")
            win.exec()
        
    def open_module(self, key: str):
        """Central router: swap to the correct panel/window for a module key.
        Replace prints with your real show-panel logic.
        """
        print(f"[OpenModule] {key}")

        # TODO: map keys to real handlers, e.g.:
        # if key == "operations.taskings":
        #     self._open_modeless(TaskStatusPanel(self), title="Taskings")
        # elif key == "logistics.requests":
        #     self._open_modeless(
        #         QmlWindow("modules/logistics/qml/requests.qml", "Resource Requests"),
        #         title="Resource Requests"
        #     )
        # else:
        #     self._open_modeless(QmlWindow("modules/common/qml/placeholder.qml", key), title=key)

        handlers: dict[str, Callable[[], None]] = {
            # ----- Menu -----
            "menu.new_mission": lambda: new_mission_form(),
            "menu.open_mission": lambda: open_mission_list(self),
            "menu.save_mission": lambda: print("[OpenModule] Save Mission not implemented yet"),
            "menu.settings": self.open_settings_window,
            "menu.exit": lambda: QApplication.instance().quit(),

            # ----- Edit -----
            "edit.ems_hospitals": self.open_settings_window,
            "edit.canned_comm_entries": self.open_settings_window,
            "edit.personnel": self.open_logistics,
            "edit.objectives": self.open_settings_window,
            "edit.task_types": self.open_settings_window,
            "edit.team_types": self.open_settings_window,
            "edit.vehicles": self.open_logistics,
            "edit.equipment": self.open_logistics,
            "communications.217": self.open_public_info,  # placeholder

            # ----- Command -----
            "command.unit_log": self.open_ics214,  # ICS-214
            "command.incident_overview": lambda: self._open_modeless(TeamStatusPanel(), title="Incident Overview"),
            "command.iap": self.open_public_info,         # placeholder
            "command.objectives": lambda: self._open_modeless(TaskStatusPanel(), title="Incident Objectives"),
            "command.staff_org": self.open_public_info,   # placeholder
            "command.sitrep": self.open_public_info,      # placeholder

            # ----- Planning -----
            "planning.unit_log": self.open_ics214,        # ICS-214
            "planning.dashboard": lambda: self._open_modeless(TaskStatusPanel(), title="Planning Dashboard"),
            "planning.approvals": self.open_public_info,  # placeholder
            "planning.forecast": self.open_public_info,   # placeholder
            "planning.op_manager": self.open_public_info, # placeholder
            "planning.taskmetrics": lambda: self._open_modeless(TaskStatusPanel(), title="Task Metrics Dashboard"),
            "planning.strategic_objectives": lambda: self._open_modeless(TaskStatusPanel(), title="Strategic Objective Tracker"),
            "planning.sitrep": self.open_public_info,     # placeholder

            # ----- Operations -----
            "operations.unit_log": self.open_ics214,      # ICS-214
            "operations.dashboard": lambda: self._open_modeless(TeamStatusPanel(), title="Assignments Dashboard"),
            "operations.team_assignments": lambda: self._open_modeless(TeamStatusPanel(), title="Team Assignments"),

            # ----- Logistics -----
            "logistics.unit_log": self.open_ics214,       # ICS-214
            "logistics.dashboard": self.open_logistics,
            "logistics.211": self.open_logistics,         # Check-In ICS-211 lives in Logistics panel
            "logistics.requests": self.open_logistics,
            "logistics.equipment": self.open_logistics,
            "logistics.213rr": lambda: self._open_modeless(ResourceRequestPanel(), title="Resource Request (ICS-213RR)"),

            # ----- Communications -----
            "comms.unit_log": self.open_ics214,           # ICS-214
            "comms.chat": self.open_public_info,          # placeholder until Comms UI
            "comms.213": self.open_public_info,           # placeholder (ICS-213 messages)
            "comms.205": self.open_public_info,           # placeholder (ICS-205)

            # ----- Intel -----
            "intel.unit_log": self.open_ics214,           # ICS-214
            "intel.dashboard": self.open_ics214,          # placeholder
            "intel.clue_log": self.open_clue_log,
            "intel.add_clue": self.open_add_clue,

            # ----- Medical & Safety -----
            "medical.unit_log": self.open_ics214,
            "safety.unit_log": self.open_ics214,
            "medical.206": self.open_safety,              # handled in Safety/Medical panel
            "safety.208": self.open_safety,
            "safety.215A": self.open_safety,
            "safety.caporm": self.open_safety,

            # ----- Liaison -----
            "liaison.unit_log": self.open_ics214,
            "liaison.agencies": self.open_public_info,    # placeholder
            "liaison.requests": self.open_public_info,    # placeholder

            # ----- Public Information -----
            "public.unit_log": self.open_ics214,
            "public.media_releases": self.open_public_info,
            "public.inquiries": self.open_public_info,

            # ----- Finance/Admin -----
            "finance.unit_log": self.open_ics214,
            "finance.time": self.open_finance,
            "finance.procurement": self.open_finance,
            "finance.summary": self.open_finance,

            # ----- Toolkits -----
            "toolkit.sar.missing_person": self.open_planned_toolkit,
            "toolkit.sar.pod": self.open_planned_toolkit,
            "toolkit.disaster.damage": self.open_planned_toolkit,
            "toolkit.disaster.urban_interview": self.open_planned_toolkit,
            "toolkit.disaster.photos": self.open_planned_toolkit,
            "planned.promotions": self.open_planned_toolkit,
            "planned.vendors": self.open_planned_toolkit,
            "planned.safety": self.open_planned_toolkit,
            "planned.tasking": self.open_planned_toolkit,
            "planned.health_sanitation": self.open_planned_toolkit,
            "toolkit.initial.hasty": self.open_planned_toolkit,
            "toolkit.initial.reflex": self.open_planned_toolkit,

            # ----- Forms & Library -----
            "forms": self.open_reference_library,         # using Reference Library panel for now
            "library": self.open_reference_library,
            "help.user_guide": self.open_public_info,     # placeholder

            # ----- Help -----
            "help.about": self.open_public_info,          # placeholder
        }

        handler = handlers.get(key)
        if handler:
            handler()
        else:
            print(f"[OpenModule] no handler for {key}")


    def _add_action(self, menu: QMenu, text: str, keyseq: str | None, module_key: str):
        act = QAction(text, self)
        if keyseq:
            act.setShortcut(QKeySequence(keyseq))
        # store module key so we can enable/disable later
        act.setData({"module_key": module_key})
        act.triggered.connect(lambda: self.open_module(module_key))
        menu.addAction(act)
        return act

    def init_module_menus(self):
        """Builds the full module menu structure in QtWidgets (keeps UI in Python)."""
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
        self._add_action(m_log, "Resource Requests", "Ctrl+L", "logistics.requests")
        self._add_action(m_log, "Equipment Inventory", None, "logistics.equipment")
        self._add_action(m_log, "Resource Requests", None, "logistics.213rr")

        # ----- Communications -----
        m_comms = mb.addMenu("Communications")
        self._add_action(m_comms, "Communications Unit Log ICS-214", None, "comms.unit_log")
        m_comms.addSeparator()
        self._add_action(m_comms, "Messaging", None, "comms.chat")
        self._add_action(m_comms, "ICS 213 Messages", None, "comms.213")
        self._add_action(m_comms, "Communications Plan ICS-205", None, "comms.205")

        # ----- Intel & Mapping -----
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
        m_forms = mb.addMenu("Resources")
        self._add_action(m_forms, "Form Library", None, "forms")
        self._add_action(m_forms, "Reference Library", None, "library")
        m_forms.addSeparator()
        self._add_action(m_forms, "User Guide", None, "help.user_guide")

        # ----- Help -----
        m_help = mb.addMenu("Help")
        self._add_action(m_help, "About", None, "help.about")
        self._add_action(m_help, "User Guide", None, "help.user_guide")

        # Example: grey-out items you haven't built yet
        self._gate_menus_by_availability({
           # "mobile": False,
            #"toolkit.disaster.damage": False,
           # "planned.promotions": False,
           # "planned.vendors": False,
            #"planned.safety": False,
        })

    def _gate_menus_by_availability(self, enabled_map: dict[str, bool]):
        """Grey-out actions whose module keys are disabled in enabled_map."""
        for menu in self.menuBar().findChildren(QMenu):
            for act in menu.actions():
                data = act.data()
                if isinstance(data, dict) and "module_key" in data:
                    key = data["module_key"]
                    if key in enabled_map:
                        act.setEnabled(bool(enabled_map[key]))

    def _find_action_by_text(self, texts: list[str]) -> QAction | None:
        """Search the menu bar for an action matching any text candidate."""
        targets = {t.strip().lower() for t in texts}

        def search(actions: list[QAction]) -> QAction | None:
            for act in actions:
                if act.text().strip().lower() in targets:
                    return act
                submenu = act.menu()
                if submenu:
                    found = search(submenu.actions())
                    if found:
                        return found
            return None

        return search(self.menuBar().actions())

    def _bind_action(self, name_candidates: list[str], slot: Callable) -> None:
        """Bind the first matching action to ``slot``."""
        action: QAction | None = None
        for candidate in name_candidates:
            action = self.findChild(QAction, candidate)
            if action:
                break
        if not action:
            action = self._find_action_by_text(name_candidates)

        if action:
            try:  # Remove existing connections if any
                action.triggered.disconnect()
            except Exception:
                pass
            action.triggered.connect(slot)
        else:
            logger.warning("Unable to locate action for %s", name_candidates)

    def _open_modeless(self, widget: QWidget, title: str) -> None:
        """Display *widget* as a modeless window, tracking it for cleanup."""
        # Attempt to use any provided docking/MDI helpers first
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
            # Focus the existing dock; replace content in case caller created a fresh widget
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


    def open_logistics(self) -> None:
        from modules import logistics

        mission_id = getattr(self, "current_mission_id", None)
        panel = logistics.get_logistics_panel(mission_id)
        self._open_modeless(panel, title="Logistics")

    def open_safety(self) -> None:
        from modules import safety

        mission_id = getattr(self, "current_mission_id", None)
        panel = safety.get_safety_panel(mission_id)
        self._open_modeless(panel, title="Safety")

    def open_reference_library(self) -> None:
        from modules import referencelibrary

        mission_id = getattr(self, "current_mission_id", None)
        panel = referencelibrary.get_library_panel()
        self._open_modeless(panel, title="Reference Library")

    def open_planned_toolkit(self) -> None:
        from modules import plannedtoolkit

        mission_id = getattr(self, "current_mission_id", None)
        panel = plannedtoolkit.get_planned_toolkit_panel()
        self._open_modeless(panel, title="Planned Event Toolkit")

    def open_finance(self) -> None:
        from modules import finance

        mission_id = getattr(self, "current_mission_id", None)
        panel = finance.get_finance_panel(mission_id)
        self._open_modeless(panel, title="Finance")

    def open_public_info(self) -> None:
        mission_id = getattr(self, "current_mission_id", None)
        try:
            from modules import public_info
        except ImportError:
            logger.warning("Public info module not available")
            return

        panel = public_info.get_public_info_panel(mission_id)
        self._open_modeless(panel, title="Public Information")

    def open_task_detail(self):
        self.task_window = QQuickView()
        self.task_window.setSource(QUrl("modules/operations/qml/taskdetail.qml"))
        self.task_window.setResizeMode(QQuickView.SizeRootObjectToView)
        self.task_window.setColor("white")
        self.task_window.show()

    def update_title_with_active_mission(self):
        print("[DEBUG] update_title_with_active_mission called")
        mission_number = AppState.get_active_mission()
        print(f"[DEBUG] Active mission number: {mission_number}")
        if mission_number:
                mission = get_mission_by_number(mission_number)
                if mission:
                    print(f"[DEBUG] Setting title to: {mission['number']}: {mission['name']}")
                    self.setWindowTitle(f"SARApp - {mission['number']}: {mission['name']}")
                else:
                    print("[DEBUG] No mission found with that number")
        else:
                print("[DEBUG] No active mission number set")

    def open_settings_window(self):
        from PySide6.QtQml import QQmlApplicationEngine

        # Create engine and attach global context
        self.settings_engine = QQmlApplicationEngine()
        settings_manager = SettingsManager()
        self.settings_bridge = QmlSettingsBridge(settings_manager)
        self.settings_engine.rootContext().setContextProperty(
            "settingsBridge", self.settings_bridge
        )

        # Load the QML file
        self.settings_engine.load(QUrl.fromLocalFile("qml/settingswindow.qml"))

        if not self.settings_engine.rootObjects():
            print("[ERROR] Failed to load settings QML.")
            return

        window = self.settings_engine.rootObjects()[0]
        window.show()

if __name__ == "__main__":
        app = QApplication(sys.argv)

        # Global settingsBridge setup
        settings_manager = SettingsManager()
        settings_bridge = QmlSettingsBridge(settings_manager)

        win = MainWindow(settings_manager=settings_manager, settings_bridge=settings_bridge)
        win.show()
        sys.exit(app.exec())

