from __future__ import annotations

from PySide6.QtWidgets import QWidget

from .panels.finance_admin_panel import FinanceAdminPanel

__all__ = [
    "get_time_panel",
    "get_procurement_panel",
    "get_summary_panel",
    "get_finance_panel",
]


def _panel(incident_id: object | None, default_tab: str) -> QWidget:
    return FinanceAdminPanel(str(incident_id or "UNASSIGNED"), default_tab=default_tab)


def get_time_panel(incident_id: object | None = None) -> QWidget:
    return _panel(incident_id, "dashboard")


def get_procurement_panel(incident_id: object | None = None) -> QWidget:
    return _panel(incident_id, "expenses")


def get_summary_panel(incident_id: object | None = None) -> QWidget:
    return _panel(incident_id, "reports")


def get_finance_panel(incident_id: object | None = None) -> QWidget:
    return _panel(incident_id, "dashboard")

