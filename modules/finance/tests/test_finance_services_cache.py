from __future__ import annotations

import pytest

from modules.finance import services
from utils.incident_cache import incident_cache


def _failing_get(*args, **kwargs):
    raise AssertionError("service should use the active incident cache")


@pytest.fixture(autouse=True)
def _clear_incident_cache(monkeypatch):
    incident_cache.clear()
    monkeypatch.setattr(services, "_client", lambda: _FailingClient())
    yield
    incident_cache.clear()


class _FailingClient:
    def get(self, *args, **kwargs):
        raise AssertionError("service should use the active incident cache")


def test_list_forecasts_reads_from_cache_sorted():
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "finance_forecasts": [
                {
                    "_id": "f-1", "int_id": 1, "incident_id": "INC-CACHE",
                    "forecast_name": "Older", "forecast_type": "Fuel", "category": "Fuel",
                    "status": "Draft", "total_estimated_cost": 100.0, "total_estimated_gallons": 10.0,
                    "created_at": "2026-07-01T00:00:00+00:00",
                },
                {
                    "_id": "f-2", "int_id": 2, "incident_id": "INC-CACHE",
                    "forecast_name": "Newer", "forecast_type": "Fuel", "category": "Fuel",
                    "status": "Submitted", "total_estimated_cost": 200.0, "total_estimated_gallons": 20.0,
                    "created_at": "2026-07-05T00:00:00+00:00",
                },
            ]
        },
    )

    forecasts = services.list_forecasts("INC-CACHE")
    assert [f.forecast_name for f in forecasts] == ["Newer", "Older"]

    single = services.get_forecast("INC-CACHE", 1)
    assert single.forecast_name == "Older"


def test_list_expenses_and_attachments_from_cache():
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "finance_expenses": [
                {
                    "_id": "e-1", "int_id": 1, "incident_id": "INC-CACHE",
                    "category": "Fuel", "description": "Gas fill-up", "expense_datetime": "2026-07-01T00:00:00+00:00",
                    "amount_subtotal": 50.0, "amount_tax": 0, "amount_tip": 0, "amount_total": 50.0,
                    "status": "Draft", "entered_at": "2026-07-01T00:00:00+00:00", "receipt_attached": False,
                    "expense_number": "EXP-0001",
                },
            ],
            "finance_attachments": [
                {
                    "_id": "a-1", "int_id": 1, "incident_id": "INC-CACHE",
                    "record_type": "expense", "record_id": 1, "filename": "receipt.pdf",
                    "file_path": "/tmp/receipt.pdf", "uploaded_at": "2026-07-01T01:00:00+00:00",
                },
                {
                    "_id": "a-2", "int_id": 2, "incident_id": "INC-CACHE",
                    "record_type": "forecast", "record_id": 9, "filename": "other.pdf",
                    "file_path": "/tmp/other.pdf", "uploaded_at": "2026-07-01T01:00:00+00:00",
                },
            ],
        },
    )

    expenses = services.list_expenses("INC-CACHE")
    assert [e.description for e in expenses] == ["Gas fill-up"]

    expense = services.get_expense("INC-CACHE", 1)
    assert expense.expense_number == "EXP-0001"

    attachments = services.list_attachments("INC-CACHE", "expense", 1)
    assert [a.filename for a in attachments] == ["receipt.pdf"]


def test_dashboard_snapshot_aggregates_from_cache():
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "finance_forecasts": [
                {
                    "_id": "f-1", "int_id": 1, "incident_id": "INC-CACHE",
                    "forecast_name": "Fuel Plan", "category": "Fuel", "status": "Submitted",
                    "total_estimated_cost": 300.0, "total_estimated_gallons": 30.0,
                    "created_at": "2026-07-01T00:00:00+00:00",
                },
            ],
            "finance_expenses": [
                {
                    "_id": "e-1", "int_id": 1, "incident_id": "INC-CACHE",
                    "category": "Fuel", "description": "Gas", "expense_datetime": "2026-07-01T00:00:00+00:00",
                    "amount_subtotal": 40.0, "amount_total": 40.0, "status": "Submitted",
                    "entered_at": "2026-07-01T00:00:00+00:00", "receipt_attached": False,
                    "expense_number": "EXP-0001",
                },
            ],
        },
    )

    snapshot = services.get_dashboard_snapshot("INC-CACHE")
    assert snapshot.total_forecast_cost == 300.0
    assert snapshot.total_actual_cost == 40.0
    assert snapshot.fuel_forecast_cost == 300.0
    assert snapshot.fuel_actual_cost == 40.0
    assert snapshot.pending_approvals == 2
    assert snapshot.missing_receipts == 1
    assert snapshot.forecast_count == 1
    assert snapshot.expense_count == 1

    pending = services.list_pending_approvals("INC-CACHE")
    assert {(p.record_type, p.record_id) for p in pending} == {("forecast", 1), ("expense", 1)}


def test_list_forecasts_falls_back_to_api_without_active_cache(monkeypatch):
    calls: list[str] = []

    class _FakeClient:
        def get(self, path, params=None):
            calls.append(path)
            return []

    monkeypatch.setattr(services, "_client", lambda: _FakeClient())

    assert services.list_forecasts("INC-NO-CACHE") == []
    assert calls == ["/api/incidents/INC-NO-CACHE/finance/forecasts"]
