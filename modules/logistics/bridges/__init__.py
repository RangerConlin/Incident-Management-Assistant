"""Bridges exposing high level Logistics functionality."""

from .logistics_bridge import (
    set_active_incident,
    get_active_incident,
    list_personnel,
    create_or_update_personnel,
    delete_personnel,
    record_checkin,
    list_equipment,
    save_equipment,
    delete_equipment,
    list_vehicles,
    save_vehicle,
    delete_vehicle,
    list_aircraft,
    save_aircraft,
    delete_aircraft,
)

__all__ = [
    "set_active_incident",
    "get_active_incident",
    "list_personnel",
    "create_or_update_personnel",
    "delete_personnel",
    "record_checkin",
    "list_equipment",
    "save_equipment",
    "delete_equipment",
    "list_vehicles",
    "save_vehicle",
    "delete_vehicle",
    "list_aircraft",
    "save_aircraft",
    "delete_aircraft",
]
