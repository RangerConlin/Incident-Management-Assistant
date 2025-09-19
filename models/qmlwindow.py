# models/qmlwindow.py
from PySide6.QtWidgets import QDialog, QVBoxLayout
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtQml import QQmlContext
from PySide6.QtCore import QUrl
import os

from models.incident_handler import IncidentHandler
from models.incidentlist import IncidentListModel
from models.database import get_incident_by_number
from utils.state import AppState

# Import the SQLite model (support either class spelling present in your file)
try:
    from models.sqlite_table_model import SQLiteTableModel as _SQLiteModel
except ImportError:
    from models.sqlite_table_model import SqliteTableModel as _SQLiteModel


# --------------------------
# Helpers to build models
# --------------------------

_DB_PATH = os.path.join("data", "master.db")

def _make_model(sql: str):
    m = _SQLiteModel(_DB_PATH)
    m.load_query(sql)
    return m

def _window_model_map():
    """
    Returns a dict keyed by QML filename (basename) to a tuple of:
      (context_property_name, model_factory_callable)
    """
    def _ems():
        return _make_model("""
            SELECT id, name, type, phone, fax, email, contact,
                   address, city, state, zip, notes, is_active
            FROM ems
            ORDER BY name COLLATE NOCASE;
        """)

    def _hospitals():
        return _make_model("""
            SELECT id, name, address, contact_name,
                   phone_er, phone_switchboard, travel_time_min,
                   helipad, trauma_level, burn_center, pediatric_capability,
                   bed_available, diversion_status, ambulance_radio_channel,
                   notes, lat, lon
            FROM hospitals
            ORDER BY name COLLATE NOCASE;
        """)

    return {
        # Communications resources catalog
        "CommsResourcesWindow.qml": (
            "CommsResourcesModel",
            lambda: _make_model("""
                SELECT id,
                       alpha_tag, function, freq_rx, rx_tone, freq_tx, tx_tone,
                       system, mode, notes, line_a, line_c
                FROM comms_resources
                ORDER BY alpha_tag COLLATE NOCASE;
            """)
        ),

        # Canned comm entries
        "CannedCommEntriesWindow.qml": (
            "CannedCommEntriesModel",
            lambda: _make_model("""
                SELECT id, title, category, message, notification_level, status_update, is_active
                FROM canned_comm_entries
                ORDER BY category COLLATE NOCASE, title COLLATE NOCASE;
            """)
        ),

        # Team types
        "TeamTypesWindow.qml": (
            "TeamTypesModel",
            lambda: _make_model("""
                SELECT id, type_short, name, organization, is_drone, is_aviation
                FROM team_types
                ORDER BY name COLLATE NOCASE;
            """)
        ),

        # Personnel
        "PersonnelWindow.qml": (
            "PersonnelModel",
            lambda: _make_model("""
                SELECT id, name, rank, callsign, role, contact, unit, phone, email,
                       emergency_contact_name, emergency_contact_phone, emergency_contact_relation
                FROM personnel
                ORDER BY name COLLATE NOCASE;
            """)
        ),

        # Vehicles
        "VehiclesWindow.qml": (
            "VehiclesModel",
            lambda: _make_model("""
                SELECT id, vin, license_plate, year, make, model, capacity, type_id, status_id, tags, organization
                FROM vehicles
                ORDER BY make COLLATE NOCASE, model COLLATE NOCASE, year DESC;
            """)
        ),

        # Equipment
        "EquipmentWindow.qml": (
            "EquipmentModel",
            lambda: _make_model("""
                SELECT id, name, type, serial_number, condition, notes
                FROM equipment
                ORDER BY name COLLATE NOCASE;
            """)
        ),

        # EMS facilities
        "EmsWindow.qml": (
            "EMSModel",
            _ems
        ),

        # Hospitals
        "HospitalsWindow.qml": (
            "HospitalsModel",
            _hospitals
        ),

        # Certifications
        "CertificationsWindow.qml": (
            "CertificationsModel",
            lambda: _make_model("""
                SELECT id,
                       Code, name, description, category, issuing_organization, parent_certification_id
                FROM certification_types
                ORDER BY category COLLATE NOCASE, name COLLATE NOCASE;
            """)
        ),

        # Task templates
        "TaskTypesWindow.qml": (
            "TaskTypesModel",
            lambda: _make_model("""
                SELECT id, title, description, category, default_assignee_role
                FROM task_templates
                ORDER BY category COLLATE NOCASE, title COLLATE NOCASE;
            """)
        ),
        # NOTE: ObjectivesWindow / SafetyTemplatesWindow intentionally omitted (no master tables yet)
    }


# --------------------------
# QML host dialog
# --------------------------

class QmlWindow(QDialog):
    """
    Generic QML host dialog using QQuickWidget.
    Pass context_data as a dict of {name: object} to expose to QML.
    If context_data is None or missing a known model for this window, we will auto-inject it.
    """
    def __init__(self, qml_path, title, context_data=None):
        super().__init__()
        self.setWindowTitle(title)
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.qml_widget = QQuickWidget()
        context: QQmlContext = self.qml_widget.rootContext()

        # Start with any provided context_data
        if context_data is None:
            context_data = {}

        # Auto-inject a model if this QML filename is recognized and the key is missing
        filename = os.path.basename(qml_path)
        mdl_map = _window_model_map()
        if filename in mdl_map:
            key, factory = mdl_map[filename]
            if key not in context_data:
                try:
                    context_data[key] = factory()
                except Exception as e:
                    print(f"[qmlwindow] failed to build model for {filename}: {e}")

        # Apply context properties
        for k, v in context_data.items():
            context.setContextProperty(k, v)

        # Load QML
        self.qml_widget.setSource(QUrl.fromLocalFile(os.path.abspath(qml_path)))
        self.qml_widget.setResizeMode(QQuickWidget.SizeRootObjectToView)
        layout.addWidget(self.qml_widget)


# --------------------------
# Incident dialogs (unchanged)
# --------------------------

def new_incident_form():
    path = os.path.abspath("qml/newincidentform.qml")
    win = QmlWindow(path, "Create New Incident", {
        "incidentHandler": IncidentHandler()
    })
    win.exec()


def open_incident_list(main_window=None):
    model = IncidentListModel()
    model.refresh()

    handler = IncidentHandler()

    def handle_selection(incident_number):
        AppState.set_active_incident(incident_number)
        incident = get_incident_by_number(incident_number)
        if incident:
            print(f"Selected incident: {incident['number']} - {incident['name']}")
            if main_window:
                main_window.update_title_with_active_incident()

    handler.incidentselected.connect(handle_selection)

    path = os.path.abspath("qml/incidentlist.qml")
    win = QmlWindow(path, "Select Active Incident", {
        "incidentModel": model,
        "incidentHandler": handler
    })
    root = win.qml_widget.rootObject()
    root.incidentselected.connect(handler.select_incident)
    win.exec()


# ---------------------------------------
# Convenience launchers for master windows
# (optional: your menu can call these)
# ---------------------------------------

def open_comms_resources():
    path = os.path.abspath("qml/CommsResourcesWindow.qml")
    win = QmlWindow(path, "Communications Resources")
    win.exec()

def open_canned_comm_entries():
    path = os.path.abspath("qml/CannedCommEntriesWindow.qml")
    win = QmlWindow(path, "Canned Communications Entries")
    win.exec()

def open_team_types():
    path = os.path.abspath("qml/TeamTypesWindow.qml")
    win = QmlWindow(path, "Team Types")
    win.exec()

def open_personnel():
    path = os.path.abspath("qml/PersonnelWindow.qml")
    win = QmlWindow(path, "Personnel Catalog")
    win.exec()

def open_vehicles():
    from modules.logistics.vehicle.panels.vehicle_edit_window import VehicleEditDialog

    win = VehicleEditDialog()
    win.exec()

def open_aircraft():
    from modules.logistics.aircraft.panels.aircraft_inventory_window import (
        AircraftInventoryWindow,
    )

    win = AircraftInventoryWindow()
    win.exec()

def open_equipment():
    path = os.path.abspath("qml/EquipmentWindow.qml")
    win = QmlWindow(path, "Equipment Catalog")
    win.exec()

def open_ems():
    path = os.path.abspath("qml/EmsWindow.qml")
    win = QmlWindow(path, "EMS Facilities")
    win.exec()

def open_hospitals():
    path = os.path.abspath("qml/HospitalsWindow.qml")
    win = QmlWindow(path, "Hospitals Catalog")
    win.exec()

def open_certifications():
    path = os.path.abspath("qml/CertificationsWindow.qml")
    win = QmlWindow(path, "Certification Types")
    win.exec()

def open_task_types():
    path = os.path.abspath("qml/TaskTypesWindow.qml")
    win = QmlWindow(path, "Task Templates")
    win.exec()
