"""Router-level tests for Logistics Resource Requests — focused on the
FINANCE_APPROVE -> Finance Estimate creation wiring added alongside the
canonical Budget/Estimate/Actual-Cost model (see
docs/archive/design-documents/Instructions/finance_architecture.md)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[4]))

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sarapp_db.api.routers import finance, logistics_resource_requests


class _FakeRepository:
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

    def find(self, query: dict[str, Any] | None = None, projection=None, sort=None):
        matches = [d for d in self.docs if self._matches(d, query or {})]
        for key, direction in reversed(sort or []):
            matches.sort(key=lambda d: d.get(key) or 0, reverse=direction < 0)
        return [dict(d) for d in matches]

    def find_one(self, query: dict[str, Any], sort=None, **_: Any):
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
        return self.find(query, sort=sort)

    def find_by_id(self, doc_id, **_: Any):
        for d in self.docs:
            if d.get("_id") == doc_id:
                return dict(d)
        return None

    def apply_update(self, doc_id, update: dict[str, Any], *, array_filters=None, extra_filter=None, **_: Any) -> bool:
        for d in self.docs:
            if d.get("_id") != doc_id:
                continue
            for op, fields in update.items():
                if op == "$set":
                    for key, value in fields.items():
                        if "." in key and array_filters:
                            self._apply_array_filter_set(d, key, value, array_filters)
                        else:
                            d[key] = value
                elif op == "$push":
                    for key, value in fields.items():
                        d.setdefault(key, [])
                        if isinstance(value, dict) and "$each" in value:
                            d[key].extend(value["$each"])
                        else:
                            d[key].append(value)
            return True
        return False

    @staticmethod
    def _apply_array_filter_set(doc: dict[str, Any], key: str, value: Any, array_filters: list[dict[str, Any]]) -> None:
        # key looks like "items.$[item].estimate_id"
        parts = key.split(".")
        array_name = parts[0]
        field_name = parts[-1]
        filter_field, filter_value = next(iter(array_filters[0].items()))
        filter_field = filter_field.split(".")[-1]
        for element in doc.get(array_name, []):
            if element.get(filter_field) == filter_value:
                element[field_name] = value

    def update_one(self, doc_id, updates: dict[str, Any], **_: Any) -> bool:
        return self.apply_update(doc_id, {"$set": updates})

    def count(self, query: dict[str, Any] | None = None, **_: Any) -> int:
        return len(self.find(query))


def _client(monkeypatch):
    requests_repo = _FakeRepository()
    estimates_repo = _FakeRepository()

    monkeypatch.setattr(logistics_resource_requests, "_repo", lambda _incident_id: requests_repo)
    monkeypatch.setattr(finance, "_estimates_repo", lambda _incident_id: estimates_repo)

    app = FastAPI()
    app.include_router(logistics_resource_requests.router, prefix="/api")
    app.include_router(finance.router, prefix="/api")
    return TestClient(app), requests_repo, estimates_repo


def _create_request_with_cost_item(client) -> dict:
    created = client.post(
        "/api/incidents/INC-1/logistics/resource-requests",
        json={
            "title": "2 portable radios",
            "requesting_section": "operations",
            "priority": "HIGH",
            "created_by_id": "7",
            "items": [
                {"kind": "EQUIPMENT", "description": "Portable radio", "quantity": 2, "unit": "each",
                 "estimated_unit_cost": 400.0, "estimated_total_cost": 800.0},
            ],
        },
    )
    assert created.status_code == 201
    return created.json()


def test_finance_approve_creates_linked_committed_estimate(monkeypatch):
    client, _requests_repo, _estimates_repo = _client(monkeypatch)
    request = _create_request_with_cost_item(client)

    approved = client.post(
        f"/api/incidents/INC-1/logistics/resource-requests/{request['id']}/approvals",
        json={"action": "FINANCE_APPROVE", "actor_id": "finance-1"},
    )
    assert approved.status_code == 201

    refreshed = client.get(f"/api/incidents/INC-1/logistics/resource-requests/{request['id']}").json()
    item = refreshed["items"][0]
    assert item["estimate_id"] is not None

    estimates = client.get(
        "/api/incidents/INC-1/finance/estimates", params={"resource_request_id": request["id"]},
    ).json()
    assert len(estimates) == 1
    estimate = estimates[0]
    assert estimate["id"] == item["estimate_id"]
    assert estimate["status"] == "committed"
    assert estimate["original_amount"] == 800.0
    assert estimate["resource_request_item_id"] == item["id"]


def test_finance_approve_does_not_duplicate_existing_estimate(monkeypatch):
    client, _requests_repo, _estimates_repo = _client(monkeypatch)
    request = _create_request_with_cost_item(client)

    client.post(
        f"/api/incidents/INC-1/logistics/resource-requests/{request['id']}/approvals",
        json={"action": "FINANCE_APPROVE", "actor_id": "finance-1"},
    )
    client.post(
        f"/api/incidents/INC-1/logistics/resource-requests/{request['id']}/approvals",
        json={"action": "FINANCE_APPROVE", "actor_id": "finance-1", "note": "re-approved"},
    )

    estimates = client.get(
        "/api/incidents/INC-1/finance/estimates", params={"resource_request_id": request["id"]},
    ).json()
    assert len(estimates) == 1


def test_finance_approve_skips_items_without_cost_impact(monkeypatch):
    client, _requests_repo, _estimates_repo = _client(monkeypatch)
    created = client.post(
        "/api/incidents/INC-1/logistics/resource-requests",
        json={
            "title": "General supplies",
            "requesting_section": "operations",
            "priority": "LOW",
            "created_by_id": "7",
            "items": [{"kind": "SUPPLY", "description": "Zip ties", "quantity": 10, "unit": "each"}],
        },
    ).json()

    client.post(
        f"/api/incidents/INC-1/logistics/resource-requests/{created['id']}/approvals",
        json={"action": "FINANCE_APPROVE", "actor_id": "finance-1"},
    )

    refreshed = client.get(f"/api/incidents/INC-1/logistics/resource-requests/{created['id']}").json()
    assert refreshed["items"][0].get("estimate_id") is None
