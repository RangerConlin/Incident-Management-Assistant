"""Headless Qt smoke tests for the Finance/Admin panels — construct them
with every service call mocked, so this catches Qt wiring bugs (missing
widgets, bad signal connections) without touching the network or Mongo."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from modules.finance import services
from modules.finance.models.schemas import BudgetSummaryRead


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _mock_services(monkeypatch):
    monkeypatch.setattr(
        services, "get_budget",
        lambda _incident_id: BudgetSummaryRead(
            total_budget=10000.0, open_estimated_cost=0.0, open_committed_cost=0.0,
            actual_cost=0.0, projected_incident_cost=0.0, remaining_budget=10000.0,
            projected_budget_variance=10000.0,
        ),
    )
    monkeypatch.setattr(services, "list_estimates", lambda *a, **k: [])
    monkeypatch.setattr(services, "list_actual_cost_documents", lambda *a, **k: [])
    monkeypatch.setattr(services, "list_pending_approvals", lambda *a, **k: [])
    monkeypatch.setattr(services, "list_rate_tables", lambda *a, **k: [])
    yield


def test_finance_admin_panel_constructs_and_navigates():
    from modules.finance.panels.finance_admin_panel import FinanceAdminPanel

    panel = FinanceAdminPanel("INC-TEST")
    assert panel.pages.count() == len(FinanceAdminPanel.NAV_ITEMS)
    panel._select_page("estimates")
    assert panel.pages.currentIndex() == panel.page_index["estimates"]
    panel._select_page("actual_costs")
    assert panel.pages.currentIndex() == panel.page_index["actual_costs"]


def test_rate_tables_panel_constructs_and_refreshes():
    from modules.finance.panels.rate_tables_panel import RateTablesPanel

    panel = RateTablesPanel("INC-TEST")
    assert panel.table.columnCount() == 10
    panel.refresh()
    assert panel.table.rowCount() == 0
