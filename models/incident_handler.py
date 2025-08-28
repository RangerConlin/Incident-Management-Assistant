from PySide6.QtCore import QObject, Slot, Signal
from models.incident import Incident
from models.database import insert_new_incident, get_incident_by_number
from utils.incident_db import create_incident_database
from utils.state import AppState


class IncidentHandler(QObject):
    incidentselected = Signal(str)  # Emit incident number as str

    def __init__(self):
        super().__init__()

    @Slot(str, str, str, str, str, bool)
    def create_incident(self, number, name, mtype, description, icp_location, is_training):
        new_incident = Incident(
            id=None,
            number=number,
            name=name,
            type=mtype,
            description=description,
            status="Active",
            icp_location=icp_location,
            start_time=None,
            end_time=None,
            is_training=is_training
        )
        incident_id = insert_new_incident(
            new_incident.number,
            new_incident.name,
            new_incident.type,
            new_incident.description,
            new_incident.icp_location,
            new_incident.is_training
        )
        incident_number = new_incident.number
        create_incident_database(incident_number)
        AppState.set_active_incident(incident_number)
        print(f" Incident '{name}' created with ID {incident_id} and number {incident_number}")

    @Slot(str)
    def select_incident(self, incident_number):
        AppState.set_active_incident(incident_number)
        incident = get_incident_by_number(incident_number)
        if incident:
            print(f"Selected incident: {incident['number']} - {incident['name']}")
        else:
            print("Incident number not found.")
        self.incidentselected.emit(incident_number)  # Notify QML
