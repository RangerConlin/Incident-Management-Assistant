"""Router-level tests for the canonical Finance/Admin Budget/Estimate/
Actual-Cost model (rate tables, estimates, actual-cost linking/satisfaction
math, budget summary)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[4]))

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sarapp_db.api.routers import finance


class _FakeRepository:
    """Minimal in-memory stand-in for BaseRepository, enough to exercise the
    finance router's int_id-keyed documents without a real Mongo instance."""

    def __init__(self) -> None:
        self._col = self
        self.docs: list[dict[str, Any]] = []
        self._next_oid = 1

    def _matches(self, doc: dict[str, Any], query: dict[str, Any]) -> bool:
        for key, expected in query.items():
            value = doc.get(key)
            if isinstance(expected, dict):
                if "$exists" in expected and (key in doc) is not expected["$exists"]:
                    return False
                if "$ne" in expected and value == expected["$ne"]:
                    return False
                continue
            if value != expected:
                return False
        return True

    def find_one(self, query: dict[str, Any], sort: list[tuple[str, int]] | None = None, **_: Any):
        matches = [d for d in self.docs if self._matches(d, query)]
        if not matches:
            return None
        if sort:
            key, direction = sort[0]
            matches.sort(key=lambda d: d.get(key) or 0, reverse=direction < 0)
        return dict(matches[0])

    def insert_one(self, doc: dict[str, Any]) -> dict[str, Any]:
        stored = dict(doc)
        stored.setdefault("_id", f"oid-{self._next_oid}")
        self._next_oid += 1
        self.docs.append(stored)
        return dict(stored)

    def find_many(self, query: dict[str, Any] | None = None, sort=None, **_: Any) -> list[dict[str, Any]]:
        matches = [d for d in self.docs if self._matches(d, query or {})]
        for key, direction in reversed(sort or []):
            matches.sort(key=lambda d: d.get(key) or 0, reverse=direction < 0)
        return [dict(d) for d in matches]

    def find_by_id(self, doc_id, **_: Any):
        for d in self.docs:
            if d.get("_id") == doc_id:
                return dict(d)
        return None

    def update_one(self, doc_id, updates: dict[str, Any], **_: Any) -> bool:
        for d in self.docs:
            if d.get("_id") == doc_id:
                d.update(updates)
                return True
        return False

    def count(self, query: dict[str, Any] | None = None, **_: Any) -> int:
        return len(self.find_many(query))


def _client(monkeypatch):
    repos: dict[str, _FakeRepository] = {
        "rate_tables": _FakeRepository(),
        "rate_templates": _FakeRepository(),
        "budgets": _FakeRepository(),
        "estimates": _FakeRepository(),
        "actual_docs": _FakeRepository(),
        "actual_lines": _FakeRepository(),
        "approvals": _FakeRepository(),
        "attachments": _FakeRepository(),
    }
    monkeypatch.setattr(finance, "_rate_tables_repo", lambda _incident_id: repos["rate_tables"])
    monkeypatch.setattr(finance, "_rate_templates_repo", lambda: repos["rate_templates"])
    monkeypatch.setattr(finance, "_budgets_repo", lambda _incident_id: repos["budgets"])
    monkeypatch.setattr(finance, "_estimates_repo", lambda _incident_id: repos["estimates"])
    monkeypatch.setattr(finance, "_actual_docs_repo", lambda _incident_id: repos["actual_docs"])
    monkeypatch.setattr(finance, "_actual_lines_repo", lambda _incident_id: repos["actual_lines"])
    monkeypatch.setattr(finance, "_approvals_repo", lambda _incident_id: repos["approvals"])
    monkeypatch.setattr(finance, "_attachments_repo", lambda _incident_id: repos["attachments"])

    app = FastAPI()
    app.include_router(finance.router, prefix="/api")
    return TestClient(app), repos


def test_create_rate_table_entry_and_calculated_estimate(monkeypatch):
    client, _repos = _client(monkeypatch)

    rate = client.post(
        "/api/incidents/INC-1/finance/rate-tables",
        json={
            "name": "Ground Team Member",
            "category": "personnel",
            "amount": 25.0,
            "unit": "hour",
            "rate_kind": "regular",
        },
    )
    assert rate.status_code == 201
    rate_id = rate.json()["id"]

    estimate = client.post(
        "/api/incidents/INC-1/finance/estimates/calculated",
        json={
            "description": "Ground team hours for Task 12",
            "rate_table_entry_id": rate_id,
            "task_id": "12",
            "quantity": 8,
        },
    )
    assert estimate.status_code == 201
    body = estimate.json()
    assert body["original_amount"] == 200.0
    assert body["remaining_amount"] == 200.0
    assert body["status"] == "estimated"
    assert body["rate_snapshot"]["amount"] == 25.0


def test_actual_cost_line_satisfies_estimate_and_closes_it(monkeypatch):
    client, _repos = _client(monkeypatch)

    estimate = client.post(
        "/api/incidents/INC-1/finance/estimates/manual",
        json={"description": "2 radios", "category": "equipment", "amount": 800.0},
    ).json()
    estimate_id = estimate["id"]

    doc = client.post(
        "/api/incidents/INC-1/finance/actual-cost-documents",
        json={"vendor": "Acme Radio Co", "document_date": "2026-11-20", "subtotal": 800.0},
    ).json()
    doc_id = doc["id"]

    line = client.post(
        f"/api/incidents/INC-1/finance/actual-cost-documents/{doc_id}/lines",
        json={
            "description": "2 portable radios",
            "category": "equipment",
            "quantity": 2,
            "unit_price": 400.0,
            "links": [{"estimate_id": estimate_id, "amount": 800.0}],
        },
    )
    assert line.status_code == 201

    refreshed = client.get(f"/api/incidents/INC-1/finance/estimates/{estimate_id}").json()
    assert refreshed["satisfied_amount"] == 800.0
    assert refreshed["remaining_amount"] == 0.0
    assert refreshed["closed"] is True
    assert refreshed["closed_reason"] == "Actual cost received"


def test_partial_satisfaction_keeps_estimate_open(monkeypatch):
    client, _repos = _client(monkeypatch)

    estimate = client.post(
        "/api/incidents/INC-1/finance/estimates/manual",
        json={"description": "Generator rental", "category": "rentals", "amount": 500.0},
    ).json()
    estimate_id = estimate["id"]

    doc = client.post(
        "/api/incidents/INC-1/finance/actual-cost-documents",
        json={"vendor": "Rental Co", "document_date": "2026-11-20", "subtotal": 200.0},
    ).json()

    client.post(
        f"/api/incidents/INC-1/finance/actual-cost-documents/{doc['id']}/lines",
        json={
            "description": "Partial payment",
            "category": "rentals",
            "quantity": 1,
            "unit_price": 200.0,
            "links": [{"estimate_id": estimate_id, "amount": 200.0}],
        },
    )

    refreshed = client.get(f"/api/incidents/INC-1/finance/estimates/{estimate_id}").json()
    assert refreshed["satisfied_amount"] == 200.0
    assert refreshed["remaining_amount"] == 300.0
    assert refreshed["closed"] is False


def test_close_estimate_requires_valid_reason(monkeypatch):
    client, _repos = _client(monkeypatch)

    estimate = client.post(
        "/api/incidents/INC-1/finance/estimates/manual",
        json={"description": "Unused lodging night", "category": "lodging", "amount": 120.0},
    ).json()

    bad = client.post(
        f"/api/incidents/INC-1/finance/estimates/{estimate['id']}/close",
        json={"closed_reason": "Not a real reason"},
    )
    assert bad.status_code == 422

    good = client.post(
        f"/api/incidents/INC-1/finance/estimates/{estimate['id']}/close",
        json={"closed_reason": "Resource not used"},
    )
    assert good.status_code == 200
    assert good.json()["closed"] is True
    assert good.json()["remaining_amount"] == 0.0


def test_budget_summary_computes_projected_cost(monkeypatch):
    client, _repos = _client(monkeypatch)

    client.put("/api/incidents/INC-1/finance/budget", json={"total_budget": 10000.0})

    client.post(
        "/api/incidents/INC-1/finance/estimates/manual",
        json={"description": "Open estimate", "category": "other", "amount": 1000.0, "status": "estimated"},
    )
    client.post(
        "/api/incidents/INC-1/finance/estimates/manual",
        json={"description": "Committed estimate", "category": "other", "amount": 500.0, "status": "committed"},
    )

    summary = client.get("/api/incidents/INC-1/finance/budget").json()
    assert summary["total_budget"] == 10000.0
    assert summary["open_estimated_cost"] == 1000.0
    assert summary["open_committed_cost"] == 500.0
    assert summary["actual_cost"] == 0.0
    assert summary["projected_incident_cost"] == 1500.0
    assert summary["remaining_budget"] == 8500.0


def test_debrief_refinement_is_idempotent(monkeypatch):
    client, _repos = _client(monkeypatch)

    body = {
        "debrief_id": "DEBRIEF-1",
        "task_id": "12",
        "description": "Air General fuel usage",
        "category": "fuel",
        "quantity": 20.0,
        "amount": 100.0,
    }
    first = client.post("/api/incidents/INC-1/finance/estimates/debrief-refinement", json=body)
    assert first.status_code == 200
    estimate_id = first.json()["id"]

    body["quantity"] = 25.0
    body["amount"] = 125.0
    second = client.post("/api/incidents/INC-1/finance/estimates/debrief-refinement", json=body)
    assert second.status_code == 200
    assert second.json()["id"] == estimate_id
    assert second.json()["original_amount"] == 125.0

    all_estimates = client.get("/api/incidents/INC-1/finance/estimates", params={"task_id": "12"}).json()
    assert len(all_estimates) == 1
