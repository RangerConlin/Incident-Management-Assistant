"""QtWidgets-based editors for catalog entities.

This package provides a common :class:`BaseEditDialog` along with specific
entity editors. Editors are intentionally light-weight so they can be invoked
from the main window without blocking other parts of the UI.
"""

from .base_dialog import BaseEditDialog
from .roles_editor import RolesEditor
from .personnel_editor import PersonnelEditor
from .vehicle_editor import VehicleEditor
from .equipment_editor import EquipmentEditor
from .team_editor import TeamEditor
from .comms_channel_editor import CommsChannelEditor
from .ems_editor import EmsEditor
from .hospitals_editor import HospitalsEditor
from .aircraft_editor import AircraftEditor
from .objectives_editor import ObjectivesEditor
from .canned_comm_editor import CannedCommEditor
from .task_types_editor import TaskTypesEditor
from .team_types_editor import TeamTypesEditor
from .safety_templates_editor import SafetyTemplatesEditor

__all__ = [
    "BaseEditDialog",
    "RolesEditor",
    "PersonnelEditor",
    "VehicleEditor",
    "EquipmentEditor",
    "TeamEditor",
    "CommsChannelEditor",
    "EmsEditor",
    "HospitalsEditor",
    "AircraftEditor",
    "ObjectivesEditor",
    "CannedCommEditor",
    "TaskTypesEditor",
    "TeamTypesEditor",
    "SafetyTemplatesEditor",
]
