"""Public exports for vehicle panels."""

from .vehicle_edit_window import VehicleEditDialog, VehicleRepository
from .vehicle_inventory_panel import VehicleInventoryDialog, VehicleInventoryWidget

__all__ = [
    "VehicleEditDialog",
    "VehicleInventoryDialog",
    "VehicleInventoryWidget",
    "VehicleRepository",
]
