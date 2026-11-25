from __future__ import annotations

from PySide6.QtWidgets import QWidget

from .panels.finance_admin_panel import FinanceAdminPanel
from .panels.rate_tables_panel import RateTablesPanel

__all__ = [
    "get_finance_panel",
    "get_estimates_panel",
    "get_actual_costs_panel",
    "get_summary_panel",
    "get_rate_tables_panel",
]


def _panel(incident_id: object | None, default_tab: str) -> QWidget:
    return FinanceAdminPanel(str(incident_id or "UNASSIGNED"), default_tab=default_tab)


def get_finance_panel(incident_id: object | None = None) -> QWidget:
    return _panel(incident_id, "dashboard")


def get_estimates_panel(incident_id: object | None = None) -> QWidget:
    return _panel(incident_id, "estimates")


def get_actual_costs_panel(incident_id: object | None = None) -> QWidget:
    return _panel(incident_id, "actual_costs")


def get_summary_panel(incident_id: object | None = None) -> QWidget:
    return _panel(incident_id, "reports")


def get_rate_tables_panel(incident_id: object | None = None) -> QWidget:
    return RateTablesPanel(str(incident_id or "UNASSIGNED"))
