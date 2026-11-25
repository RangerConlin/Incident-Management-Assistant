from __future__ import annotations

import pytest

from modules.finance import services
from utils.incident_cache import incident_cache


@pytest.fixture(autouse=True)
def _clear_incident_cache(monkeypatch):
    incident_cache.clear()
    monkeypatch.setattr(services, "_client", lambda: _FailingClient())
    yield
    incident_cache.clear()


class _FailingClient:
    def get(self, *args, **kwargs):
        raise AssertionError("service should use the active incident cache")


def test_list_rate_tables_reads_from_cache_sorted_by_category_then_name():
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "finance_rate_tables": [
                {
                    "_id": "r-1", "int_id": 1, "incident_id": "INC-CACHE",
                    "name": "Z Vehicle", "category": "vehicle", "amount": 0.5, "unit": "mile",
                    "is_active": True,
                },
                {
                    "_id": "r-2", "int_id": 2, "incident_id": "INC-CACHE",
                    "name": "Ground Team Member", "category": "personnel", "amount": 25.0, "unit": "hour",
                    "is_active": True,
                },
            ]
        },
    )

    entries = services.list_rate_tables("INC-CACHE")
    assert [e.name for e in entries] == ["Ground Team Member", "Z Vehicle"]

    personnel_only = services.list_rate_tables("INC-CACHE", category="personnel")
    assert [e.name for e in personnel_only] == ["Ground Team Member"]


def test_list_estimates_and_attachments_from_cache():
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "finance_estimates": [
                {
                    "_id": "e-1", "int_id": 1, "incident_id": "INC-CACHE",
                    "description": "2 radios", "category": "equipment", "source_type": "manual",
                    "task_id": "12", "quantity": 2, "original_amount": 800.0, "satisfied_amount": 0.0,
                    "remaining_amount": 800.0, "status": "estimated", "closed": False, "satisfied": False,
                    "calc_method": "manual", "created_at": "2026-07-01T00:00:00+00:00",
                },
            ],
            "finance_attachments": [
                {
                    "_id": "a-1", "int_id": 1, "incident_id": "INC-CACHE",
                    "record_type": "estimate", "record_id": 1, "filename": "receipt.pdf",
                    "file_path": "/tmp/receipt.pdf", "uploaded_at": "2026-07-01T01:00:00+00:00",
                },
                {
                    "_id": "a-2", "int_id": 2, "incident_id": "INC-CACHE",
                    "record_type": "actual_cost_document", "record_id": 9, "filename": "other.pdf",
                    "file_path": "/tmp/other.pdf", "uploaded_at": "2026-07-01T01:00:00+00:00",
                },
            ],
        },
    )

    estimates = services.list_estimates("INC-CACHE", task_id="12")
    assert [e.description for e in estimates] == ["2 radios"]

    estimate = services.get_estimate("INC-CACHE", 1)
    assert estimate.remaining_amount == 800.0

    attachments = services.list_attachments("INC-CACHE", "estimate", 1)
    assert [a.filename for a in attachments] == ["receipt.pdf"]


def test_list_actual_cost_documents_and_lines_from_cache():
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "finance_actual_cost_documents": [
                {
                    "_id": "d-1", "int_id": 1, "incident_id": "INC-CACHE",
                    "vendor": "Acme Radio Co", "document_date": "2026-07-01", "subtotal": 800.0,
                    "tax": 0.0, "shipping_fees": 0.0, "total": 800.0, "verification_status": "unverified",
                    "paid": False,
                },
            ],
            "finance_actual_cost_lines": [
                {
                    "_id": "l-1", "int_id": 1, "incident_id": "INC-CACHE", "document_id": 1,
                    "description": "2 radios", "category": "equipment", "quantity": 2, "unit_price": 400.0,
                    "line_subtotal": 800.0, "attributable_extra": 0.0, "linked_estimate_ids": [1],
                },
            ],
        },
    )

    docs = services.list_actual_cost_documents("INC-CACHE")
    assert [d.vendor for d in docs] == ["Acme Radio Co"]

    lines = services.list_actual_cost_lines("INC-CACHE", 1)
    assert [l.description for l in lines] == ["2 radios"]


def test_list_rate_tables_falls_back_to_api_without_active_cache(monkeypatch):
    calls: list[str] = []

    class _FakeClient:
        def get(self, path, params=None):
            calls.append(path)
            return []

    monkeypatch.setattr(services, "_client", lambda: _FakeClient())

    assert services.list_rate_tables("INC-NO-CACHE") == []
    assert calls == ["/api/incidents/INC-NO-CACHE/finance/rate-tables"]


def test_dashboard_and_task_summary_always_call_the_api(monkeypatch):
    # Budget/estimate/actual-cost aggregation math lives server-side only —
    # the cache fast-path is intentionally not duplicated for these.
    incident_cache.load_snapshot("INC-CACHE", {"finance_estimates": []})
    calls: list[str] = []

    class _FakeClient:
        def get(self, path, params=None):
            calls.append(path)
            if "task-summary" in path:
                return {
                    "task_id": "12", "estimated_total": 0.0, "committed_total": 0.0,
                    "remaining_open_estimate": 0.0, "actual_total": 0.0, "shared_actual_total": 0.0,
                }
            return {
                "total_budget": 0.0, "open_estimated_cost": 0.0, "open_committed_cost": 0.0,
                "actual_cost": 0.0, "projected_incident_cost": 0.0, "remaining_budget": 0.0,
                "projected_budget_variance": 0.0, "open_estimate_count": 0,
                "committed_pending_documentation": 0, "estimate_count": 0,
            }

    monkeypatch.setattr(services, "_client", lambda: _FakeClient())

    services.get_dashboard_snapshot("INC-CACHE")
    services.get_task_finance_summary("INC-CACHE", "12")
    assert calls == [
        "/api/incidents/INC-CACHE/finance/dashboard",
        "/api/incidents/INC-CACHE/finance/task-summary/12",
    ]
