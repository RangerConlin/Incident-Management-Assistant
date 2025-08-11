from __future__ import annotations

from .api import router
from .panels.finance_home_panel import FinanceHomePanel


def get_finance_panel() -> FinanceHomePanel:
    """Return the main Finance panel."""
    return FinanceHomePanel()

__all__ = ["router", "get_finance_panel", "FinanceHomePanel"]
