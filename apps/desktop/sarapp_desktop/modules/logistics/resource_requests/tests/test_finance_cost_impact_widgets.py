"""Cost-impact widget tests — ItemsTable's unit/total cost columns and
RequiredApprovalsTable's Finance row, added alongside the canonical Finance
Budget/Estimate/Actual-Cost model (see
docs/archive/design-documents/Instructions/finance_architecture.md)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

try:  # pragma: no cover - import guard for CI environments without Qt libs
    from PySide6 import QtWidgets
except ImportError:  # pragma: no cover
    pytest.skip("PySide6 QtWidgets is unavailable", allow_module_level=True)

from modules.logistics.resource_requests.models.enums import ApprovalAction, RequestStatus
from modules.logistics.resource_requests.api.validators import available_approval_actions
from modules.logistics.resource_requests.panels.widgets.items_table import ItemsTable, TOTAL_COST_COL, UNIT_COST_COL
from modules.logistics.resource_requests.panels.widgets.required_approvals_table import RequiredApprovalsTable


@pytest.fixture(scope="session")
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def test_items_table_round_trips_cost_fields(qt_app):
    table = ItemsTable()
    table.set_items([
        {"kind": "EQUIPMENT", "description": "Radio", "quantity": 2, "unit": "each",
         "estimated_unit_cost": 400.0, "estimated_total_cost": 800.0, "estimate_id": 7},
    ])

    assert table.item(0, UNIT_COST_COL).text() == "400.00"
    assert table.item(0, TOTAL_COST_COL).text() == "800.00"

    data = table.items_data()
    assert data[0]["estimated_unit_cost"] == "400.00"
    assert data[0]["estimated_total_cost"] == "800.00"
    assert data[0]["estimate_id"] == 7


def test_items_table_recomputes_total_on_edit(qt_app):
    table = ItemsTable()
    table.set_items([{"kind": "SUPPLY", "description": "Zip ties", "quantity": 10, "unit": "each"}])

    table.item(0, UNIT_COST_COL).setText("2.50")
    assert table.item(0, TOTAL_COST_COL).text() == "25.00"


def test_required_approvals_table_shows_finance_control_when_cost_impact_present(qt_app):
    table = RequiredApprovalsTable()
    actions = available_approval_actions(RequestStatus.SUBMITTED)
    assert ApprovalAction.FINANCE_APPROVE not in actions  # never gated by status

    items_with_cost = [{"description": "Radio", "estimated_total_cost": 800.0}]
    table.set_data([], actions, False, items_with_cost)

    finance_row = 2  # ApprovalSection order: Requesting, Logistics, Finance
    status_item = table.item(finance_row, 1)
    assert "800.00" in status_item.text()
    assert table.cellWidget(finance_row, 5) is not None  # action buttons present


def test_required_approvals_table_shows_not_required_without_cost_impact(qt_app):
    table = RequiredApprovalsTable()
    actions = available_approval_actions(RequestStatus.SUBMITTED)
    table.set_data([], actions, False, [{"description": "Zip ties"}])

    finance_row = 2
    assert table.item(finance_row, 1).text() == "Not Required"
    assert table.cellWidget(finance_row, 5) is None


def test_required_approvals_table_reflects_linked_estimate(qt_app):
    table = RequiredApprovalsTable()
    actions = available_approval_actions(RequestStatus.SUBMITTED)
    approvals = [{"action": "FINANCE_APPROVE", "section": "finance", "actor_id": "finance-1", "ts_utc": "2026-11-25T00:00:00+00:00"}]
    items = [{"description": "Radio", "estimated_total_cost": 800.0, "estimate_id": 7}]
    table.set_data(approvals, actions, False, items)

    finance_row = 2
    assert "Approve" in table.item(finance_row, 1).text()
    assert "800.00" in table.item(finance_row, 1).text()
