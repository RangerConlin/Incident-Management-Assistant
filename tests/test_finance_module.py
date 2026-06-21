from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from modules.finance import services
from modules.finance.exporter import export_fuel_report, list_artifacts
from modules.finance.repository import with_incident_session
from modules.finance.models.schemas import (
    AttachmentCreate,
    FinanceExpenseCreate,
    FinanceForecastCreate,
    FuelForecastLineCreate,
    FuelPriceProfileCreate,
)
from utils import incident_storage


@pytest.fixture()
def finance_incident(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> str:
    base = tmp_path / "data"
    monkeypatch.setenv("CHECKIN_DATA_DIR", str(base))
    incident_storage._INITIALIZED_ROOTS.clear()
    return "FIN-TEST-001"


def test_finance_fuel_forecast_and_expense_workflow(finance_incident: str) -> None:
    profile = services.create_fuel_price_profile(
        finance_incident,
        FuelPriceProfileCreate(
            gasoline_price=3.55,
            diesel_price=4.05,
            jet_a_price=5.75,
            aviation_100ll_price=6.15,
            location_note="County average",
            source_note="Manual survey",
            entered_by="tester",
            effective_at=datetime(2026, 6, 14, 12, 0, 0),
            is_active=True,
        ),
    )
    assert profile.is_active is True
    assert services.get_active_fuel_price_profile(finance_incident) is not None
    assert services.get_fuel_unit_price(finance_incident, "Gasoline") == 3.55

    forecast = services.create_forecast(
        finance_incident,
        FinanceForecastCreate(
            operational_period_id="2",
            forecast_name="Ground Team Fuel OP2",
            created_by="planner",
        ),
    )
    line = services.add_fuel_forecast_line(
        finance_incident,
        forecast.id,
        FuelForecastLineCreate(
            resource_type="Vehicle",
            resource_name="Truck 1",
            fuel_type="Gasoline",
            quantity=4,
            estimated_miles_per_resource=100,
            estimated_mpg=15,
            fuel_price=3.55,
            linked_task_id="T-12",
        ),
    )
    assert round(line.estimated_gallons, 2) == 26.67
    updated_forecast = services.get_forecast(finance_incident, forecast.id)
    assert round(updated_forecast.total_estimated_cost, 2) == 94.67

    expense = services.create_expense(
        finance_incident,
        FinanceExpenseCreate(
            category="Fuel",
            description="Fuel stop",
            vendor="Station A",
            expense_datetime=datetime(2026, 6, 14, 13, 0, 0),
            amount_subtotal=92.84,
            amount_tax=0,
            amount_tip=0,
            entered_by="finance",
            linked_forecast_id=forecast.id,
            receipt_attached=False,
        ),
    )
    attachment = services.create_attachment(
        finance_incident,
        AttachmentCreate(
            record_type="expense",
            record_id=expense.id,
            filename="receipt.jpg",
            file_path="receipts/receipt.jpg",
            uploaded_by="finance",
        ),
    )
    assert attachment.filename == "receipt.jpg"

    services.submit_forecast(finance_incident, forecast.id, "Finance/Admin")
    services.approve_forecast(finance_incident, forecast.id, "chief")
    services.submit_expense(finance_incident, expense.id, "Finance/Admin")
    pending = services.list_pending_approvals(finance_incident)
    assert len(pending) == 1
    services.approve_expense(finance_incident, expense.id, "chief")

    snapshot = services.get_dashboard_snapshot(finance_incident)
    assert round(snapshot.total_forecast_cost, 2) == 94.67
    assert round(snapshot.total_actual_cost, 2) == 92.84
    assert snapshot.pending_approvals == 0
    assert snapshot.missing_receipts == 0

    report_rows = services.get_fuel_report(finance_incident)
    assert len(report_rows) == 1
    assert round(report_rows[0].variance, 2) == -1.83

    services.mark_expense_status(finance_incident, expense.id, "Paid/Reimbursed", actor="finance")
    paid_expense = services.get_expense(finance_incident, expense.id)
    assert paid_expense.paid_at is not None

    with with_incident_session(finance_incident) as session:
        artifact = export_fuel_report(session, finance_incident)
    assert artifact["path"].endswith("fuel_report.csv")
    assert list_artifacts(finance_incident)


def test_finance_expense_rejects_unknown_linked_forecast(finance_incident: str) -> None:
    with pytest.raises(ValueError):
        services.create_expense(
            finance_incident,
            FinanceExpenseCreate(
                category="Fuel",
                description="Invalid link",
                expense_datetime=datetime(2026, 6, 15, 9, 0, 0),
                amount_subtotal=10.0,
                linked_forecast_id=9999,
            ),
        )
