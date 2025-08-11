from PySide6.QtCore import QObject, Slot, Signal
from models.mission import Mission
from models.database import insert_new_mission, get_mission_by_id
from utils.mission_db import create_mission_database
from utils.state import AppState

class MissionHandler(QObject):
    mission_selected = Signal(str)  # Emit mission_id as int

    def __init__(self):
        super().__init__()

    @Slot(str, str, str, str, str, bool)
    def create_mission(self, number, name, mtype, description, icp_location, is_training):
        new_mission = Mission(
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
        mission_id = insert_new_mission(
            new_mission.number,
            new_mission.name,
            new_mission.type,
            new_mission.description,
            new_mission.icp_location,
            new_mission.is_training
        )
        create_mission_database(mission_id)
        print(f" Mission '{name}' created with ID {mission_id}")

    @Slot(int)
    def select_mission(self, mission_id):
        AppState.set_active_mission(mission_id)
        mission = get_mission_by_id(mission_id)
        if mission:
            print(f"Selected mission: {mission['number']} - {mission['name']}")
        else:
            print("Mission ID not found.")
        self.mission_selected.emit(mission_id)  # Notify QML
