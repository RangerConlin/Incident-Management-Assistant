# main.py
import sys
from PySide6.QtWidgets import QApplication, QDockWidget, QPushButton, QMainWindow, QMenu, QLabel, QWidget, QVBoxLayout
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QUrl
from PySide6.QtQuick import QQuickView
from modules.operations.panels.team_status_panel import TeamStatusPanel
from modules.operations.panels.task_status_panel import TaskStatusPanel
from models.qmlwindow import QmlWindow, new_mission_form, open_mission_list
from utils.state import AppState
from models.database import get_mission_by_id
from bridge.settings_bridge import QmlSettingsBridge
from utils.settingsmanager import SettingsManager

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #f5f5f5;")

        self.settings_manager = settings_manager
        self.settings_bridge = settings_bridge

        # Try to load the active mission and include it in the title
        active_id = AppState.get_active_mission()
        if active_id:
            mission = get_mission_by_id(active_id)
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
        self.init_menu_bar()

    def open_ics214(self):
            win = QmlWindow("modules/intel/qml/intellog.qml", "Intel Unit Log (ICS-214)")
            win.exec()

    def open_clue_log(self):
            win = QmlWindow("modules/intel/qml/sar134.qml", "Clue Log (SAR-134)")
            win.exec()

    def open_add_clue(self):
            win = QmlWindow("modules/intel/qml/sar135.qml", "Add Clue (SAR-135)")
            win.exec()

    def init_menu_bar(self):
        menu_bar = self.menuBar()

        # File Menu
        file_menu = menu_bar.addMenu("File")

        # Add New Mission
        action_new_mission = QAction("New Mission", self)
        action_new_mission.triggered.connect(new_mission_form)
        file_menu.addAction(action_new_mission)

        # Add Open Mission
        action_open_mission = QAction("Open Mission", self)
        action_open_mission.triggered.connect(lambda: open_mission_list(self))
        file_menu.addAction(action_open_mission)

        # Settings action
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings_window)
        file_menu.addAction(settings_action)

        file_menu.addAction(QAction("Save", self))
        file_menu.addAction(QAction("Save As", self))
        file_menu.addSeparator()
        file_menu.addAction(QAction("Exit", self, triggered=self.close))

        # Edit Menu
        edit_menu = menu_bar.addMenu("Edit")
        edit_menu.addAction(QAction("Options", self))
        edit_menu.addSeparator()
        edit_menu.addAction(QAction("EMS and Hospitals", self))
        edit_menu.addAction(QAction("Canned Communication Entries", self))
        edit_menu.addAction(QAction("Objectives", self))
        edit_menu.addAction(QAction("Tasks Types", self))
        edit_menu.addAction(QAction("Team Types", self))

        # Command Menu
        command_menu = menu_bar.addMenu("Command")
        command_menu.addAction(QAction("Command Unit Log (ICS-214)", self))
        command_menu.addSeparator()
        command_menu.addAction(QAction("Incident Overview", self))
        command_menu.addAction(QAction("Incident Action Plan Builder", self))
        command_menu.addAction(QAction("Incident Objectives (ICS-202)", self))
        command_menu.addAction(QAction("Command Staff Organization (ICS-203)", self))
        command_menu.addAction(QAction("Incident Summary (ICS-209)", self))

        # Planning Menu
        planning_menu = menu_bar.addMenu("Planning")
        planning_menu.addAction(QAction("Planning Unit Log (ICS-214)", self))
        planning_menu.addSeparator()
        planning_menu.addAction(QAction("Pending Approvals", self))
        planning_menu.addAction(QAction("Planning Forecast Tool", self))
        planning_menu.addAction(QAction("Operational Period Manager", self))
        planning_menu.addAction(QAction("Task Metrics Dashboard", self))
        planning_menu.addAction(QAction("Strategic Objective Tracker", self))
        planning_menu.addAction(QAction("Planning Dashboard", self))
        planning_menu.addAction(QAction("Situation Reports", self))
        planning_menu.addAction(QAction("Strategic Tasks", self, triggered=self.open_task_detail))

        # Operations Menu
        operations_menu = menu_bar.addMenu("Operations")
        operations_menu.addAction(QAction("Operations Unit Log (ICS-214)", self))
        operations_menu.addSeparator()
        operations_menu.addAction(QAction("Tasks", self))
        operations_menu.addAction(QAction("Assign Teams", self))

        # Logistics Menu
        logistics_menu = menu_bar.addMenu("Logistics")
        logistics_menu.addAction(QAction("Logistics Unit Log (ICS-214)", self))
        logistics_menu.addSeparator()
        logistics_menu.addAction(QAction("Resource Tracker", self))
        logistics_menu.addAction(QAction("Check-In (ICS-211)", self))
        logistics_menu.addAction(QAction("Personnel", self))
        logistics_menu.addAction(QAction("Vehicles", self))
        logistics_menu.addAction(QAction("Equipment", self))
        logistics_menu.addAction(QAction("Member Needs", self))

        # Communications Menu
        comms_menu = menu_bar.addMenu("Communications")
        comms_menu.addAction(QAction("Communications Unit Log (ICS-214)", self))
        comms_menu.addSeparator()
        comms_menu.addAction(QAction("Comms Log (ICS-309)", self))
        comms_menu.addAction(QAction("Communications Plan (ICS-205)", self))

        # Intel Menu
        intel_menu = menu_bar.addMenu("Intel")

        # Action: Intel Unit Log (ICS-214)
        action_ics214 = QAction("Intel Unit Log (ICS-214)", self)
        action_ics214.triggered.connect(self.open_ics214)
        intel_menu.addAction(action_ics214)

        # Separator
        intel_menu.addSeparator()

        # Action: Clue Log (SAR-134)
        action_clue_log = QAction("Clue Log (SAR-134)", self)
        action_clue_log.triggered.connect(self.open_clue_log)
        intel_menu.addAction(action_clue_log)

        # Action: Add Clue (SAR-135)
        action_add_clue = QAction("Add Clue (SAR-135)", self)
        action_add_clue.triggered.connect(self.open_add_clue)
        intel_menu.addAction(action_add_clue)


        # Safety Menu
        safety_menu = menu_bar.addMenu("Safety")
        safety_menu.addAction(QAction("Safety Unit Log (ICS-214)", self))
        safety_menu.addSeparator()
        safety_menu.addAction(QAction("Incident Hazards", self))
        safety_menu.addAction(QAction("Safety Message (ICS-208)", self))
        safety_menu.addAction(QAction("Incident Safety Analysis (ICS-215A)", self))

        # Medical Menu
        medical_menu = menu_bar.addMenu("Medical")
        medical_menu.addAction(QAction("Medical Unit Log (ICS-214)", self))
        medical_menu.addSeparator()
        patient_tools = QMenu("Patient Tools", self)
        patient_tools.addAction(QAction("Patient Log", self))
        patient_tools.addAction(QAction("Triage Board", self))
        medical_menu.addMenu(patient_tools)
        medical_menu.addSeparator()
        medical_menu.addAction(QAction("View All Patients", self))

        # Public Information Menu
        pio_menu = menu_bar.addMenu("Public Information")
        pio_menu.addAction(QAction("PIO Unit Log (ICS-214)", self))
        pio_menu.addSeparator()
        pio_menu.addAction(QAction("Comms Log (ICS-309)", self))

        # Liaison Menu
        liaison_menu = menu_bar.addMenu("Liaison")
        liaison_menu.addAction(QAction("Liaison Officer Unit Log (ICS-214)", self))
        liaison_menu.addSeparator()
        liaison_menu.addAction(QAction("Agency Contacts", self))
        liaison_menu.addAction(QAction("Customer Requests", self))

        # Toolkits Menu
        toolkits_menu = menu_bar.addMenu("Toolkits")
        sar_tools = QMenu("SAR Tools", self)
        sar_tools.addAction(QAction("Matteson Analysis", self))
        toolkits_menu.addMenu(sar_tools)

        initialresponse_tools = QMenu("Initial Response", self)
        initialresponse_tools.addAction(QAction("Reflex Taskings", self))
        toolkits_menu.addMenu(initialresponse_tools)

        disaster_tools = QMenu("Disaster Response Tools", self)
        disaster_tools.addAction(QAction("Urban Interview Log", self))
        disaster_tools.addAction(QAction("Damage Photos", self))
        toolkits_menu.addMenu(disaster_tools)

        event_tools = QMenu("Planned Event Tools", self)
        event_tools.addAction(QAction("Messaging", self))
        event_tools.addAction(QAction("Vendors & Permitting", self))
        event_tools.addAction(QAction("Public Safety", self))
        event_tools.addAction(QAction("Tasking", self))
        event_tools.addAction(QAction("Health & Sanitation", self))
        toolkits_menu.addMenu(event_tools)

        # Resource Menu
        resource_menu = menu_bar.addMenu("Resources")
        resource_menu.addAction(QAction("Form Library", self))
        resource_menu.addAction(QAction("Resource Library", self))
        resource_menu.addSeparator()
        resource_menu.addAction(QAction("User Guide", self))
        resource_menu.addAction(QAction("About SARApp", self))

    def open_task_detail(self):
        self.task_window = QQuickView()
        self.task_window.setSource(QUrl("TaskDetail.qml"))
        self.task_window.setResizeMode(QQuickView.SizeRootObjectToView)
        self.task_window.setColor("white")
        self.task_window.show()

    def open_mission_list(self):
        win = QmlWindow("qml/missionlist.qml", "Select Mission")
        win.exec()

    def update_title_with_active_mission(self):
        print("[DEBUG] update_title_with_active_mission called")
        mission_id = AppState.get_active_mission()
        print(f"[DEBUG] Active mission ID: {mission_id}")
        if mission_id:
                mission = get_mission_by_id(mission_id)
                if mission:
                    print(f"[DEBUG] Setting title to: {mission['number']}: {mission['name']}")
                    self.setWindowTitle(f"SARApp - {mission['number']}: {mission['name']}")
                else:
                    print("[DEBUG] No mission found with that ID")
        else:
                print("[DEBUG] No active mission ID set")

    def open_settings_window(self):
        from PySide6.QtQml import QQmlApplicationEngine

        # Store the engine in self so it doesn't get garbage collected
        self.settings_engine = QQmlApplicationEngine()

        # Create engine and attach global context
        engine = QQmlApplicationEngine()
        settings_manager = SettingsManager()
        self.settings_bridge = QmlSettingsBridge(settings_manager)
        engine.rootContext().setContextProperty("settingsBridge", self.settings_bridge)

        # Load the QML file
        engine.load(QUrl.fromLocalFile("qml/settingswindow.qml"))

        if not engine.rootObjects():
            print("[ERROR] Failed to load settings QML.")
            return

        window = engine.rootObjects()[0]
        window.show()

if __name__ == "__main__":
        app = QApplication(sys.argv)

        # Global settingsBridge setup
        settings_manager = SettingsManager()
        settings_bridge = QmlSettingsBridge(settings_manager)

        win = MainWindow()
        win.show()
        sys.exit(app.exec())

