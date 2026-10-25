"""Public panel factories for the desktop Logistics module."""

from .windows import (
    get_213rr_panel,
    get_checkin_panel,
    get_facilities_manager_panel,
    get_logistics_panel,
    get_personnel_panel,
    get_quick_checkin_panel,
    get_resource_status_board_panel,
    get_vehicles_panel,
)

__all__ = [
    "get_logistics_panel",
    "get_checkin_panel",
    "get_quick_checkin_panel",
    "get_213rr_panel",
    "get_facilities_manager_panel",
    "get_personnel_panel",
    "get_vehicles_panel",
    "get_resource_status_board_panel",
]
