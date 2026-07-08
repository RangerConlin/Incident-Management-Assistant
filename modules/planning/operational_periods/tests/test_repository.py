from __future__ import annotations

import pytest

from modules.planning.operational_periods.repository import OperationalPeriodRepository
from utils.api_client import APIError


class FakeApiClient:
    """Minimal in-memory stand-in for ``utils.api_client.api_client``.

    Mirrors the overlap/active-exclusivity semantics of
    ``data/db/sarapp_db/api/routers/operational_periods.py`` so repository
    tests don't depend on a running MongoDB-backed API server.
    """

    def __init__(self):
        self.docs: dict[int, dict] = {}
        self._next_id = 1

    def _docs_for(self, incident_id: str) -> list[dict]:
        return [d for d in self.docs.values() if d["incident_id"] == incident_id]

    def _check_overlap(self, incident_id, start_time, end_time, exclude_id=None):
        from modules.planning.operational_periods.repository import _parse_dt

        start_dt = _parse_dt(start_time)
        end_dt = _parse_dt(end_time)
        for doc in self._docs_for(incident_id):
            if exclude_id is not None and doc["id"] == exclude_id:
                continue
            other_start = _parse_dt(doc.get("start_time"))
            other_end = _parse_dt(doc.get("end_time"))
            if other_start is None or other_end is None:
                continue
            if start_dt < other_end and end_dt > other_start:
                raise APIError(
                    f"Overlaps OP {doc.get('number')} ({doc.get('start_time')} to {doc.get('end_time')}).",
                    status_code=409,
                )

    def post(self, path, *, json=None):
        json = json or {}
        parts = path.strip("/").split("/")
        incident_id = parts[2]
        if path.endswith("/operational-periods"):
            start_time = str(json.get("start_time") or "")
            end_time = str(json.get("end_time") or "")
            self._check_overlap(incident_id, start_time, end_time)
            existing = self._docs_for(incident_id)
            numbers = [d["number"] for d in existing]
            number = int(json.get("number") or ((max(numbers) + 1) if numbers else 1))
            new_id = self._next_id
            self._next_id += 1
            doc = {
                "id": new_id,
                "incident_id": incident_id,
                "number": number,
                "name": json.get("name", ""),
                "status": "Planned",
                "start_time": start_time,
                "end_time": end_time,
                "created_at": "2026-06-11T00:00:00+00:00",
                "updated_at": "2026-06-11T00:00:00+00:00",
            }
            self.docs[new_id] = doc
            return dict(doc)
        if path.endswith("/set-active"):
            period_id = int(parts[-2])
            doc = self.docs[period_id]
            for other in self._docs_for(doc["incident_id"]):
                if other["id"] != period_id and other["status"] == "Active":
                    other["status"] = "Planned"
                    other["updated_at"] = "2026-06-11T01:00:00+00:00"
            doc["status"] = "Active"
            doc["updated_at"] = "2026-06-11T01:00:00+00:00"
            return dict(doc)
        raise AssertionError(f"Unexpected POST {path}")

    def get(self, path, *, params=None):
        parts = path.strip("/").split("/")
        incident_id = parts[2]
        if path.endswith("/active"):
            active = [d for d in self._docs_for(incident_id) if d["status"] == "Active"]
            active.sort(key=lambda d: d["updated_at"], reverse=True)
            return dict(active[0]) if active else None
        if path.endswith("/operational-periods"):
            return [dict(d) for d in sorted(self._docs_for(incident_id), key=lambda d: d["number"])]
        period_id = int(parts[-1])
        return dict(self.docs[period_id])


@pytest.fixture()
def fake_client(monkeypatch):
    client = FakeApiClient()
    monkeypatch.setattr("modules.planning.operational_periods.repository._client", lambda: client)
    return client


def test_repository_creates_and_sets_active_period(fake_client) -> None:
    repo = OperationalPeriodRepository(incident_id="INC-2")
    created = repo.create_period(
        {
            "number": 1,
            "start_time": "2026-06-11T07:00:00",
            "end_time": "2026-06-11T19:00:00",
            "name": "Day Shift",
        }
    )

    active = repo.set_active_period(created.id or 0)

    assert active.id == created.id
    assert active.status == "Active"
    assert repo.get_active_period() is not None
    assert repo.get_active_period().id == created.id


def test_repository_rejects_overlapping_periods(fake_client) -> None:
    repo = OperationalPeriodRepository(incident_id="INC-3")
    repo.create_period(
        {
            "number": 1,
            "start_time": "2026-06-11T07:00:00",
            "end_time": "2026-06-11T19:00:00",
        }
    )

    try:
        repo.create_period(
            {
                "number": 2,
                "start_time": "2026-06-11T18:00:00",
                "end_time": "2026-06-12T06:00:00",
            }
        )
    except ValueError as exc:
        assert "overlaps" in str(exc).lower()
    else:
        raise AssertionError("Expected overlap validation to fail")
