from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from utils.state import AppState

from modules.communications.traffic_log.models import CommsLogEntry, CommsLogQuery
from modules.communications.traffic_log.repository import ApiCommsLogRepository
from modules.communications.traffic_log.services import CommsLogService


class FakeApiClient:
    """Minimal in-memory stand-in for ``utils.api_client.api_client``."""

    def __init__(self):
        self.entries: dict[int, dict] = {}
        self.audit: dict[int, list[dict]] = {}
        self._next_id = 1

    def post(self, path, *, json=None):
        if path.endswith("/comms-log"):
            entry_id = self._next_id
            self._next_id += 1
            row = dict(json or {})
            row["id"] = entry_id
            row.setdefault("ts_utc", "2026-06-26T00:00:00+00:00")
            row.setdefault("ts_local", "2026-06-26T00:00:00")
            row.setdefault("created_at", row["ts_utc"])
            row.setdefault("updated_at", row["ts_utc"])
            self.entries[entry_id] = row
            self.audit.setdefault(entry_id, []).append({"action": "create", "changed_by": row.get("operator_user_id")})
            return dict(row)
        raise AssertionError(f"Unexpected POST {path}")

    def get(self, path, *, params=None):
        if path.endswith("/audit"):
            entry_id = int(path.split("/")[-2])
            return list(self.audit.get(entry_id, []))
        if "/comms-log/" in path:
            entry_id = int(path.rsplit("/", 1)[-1])
            return dict(self.entries[entry_id])
        if path.endswith("/comms-log"):
            rows = list(self.entries.values())
            if params and params.get("priorities"):
                wanted = set(params["priorities"].split(","))
                rows = [r for r in rows if r.get("priority") in wanted]
            return rows
        if path.endswith("/master-channels/1"):
            return {
                "id": 1,
                "name": "VHF-1",
                "display_name": "VHF-1",
                "function": "Tactical",
                "rx_freq": 155.55,
                "tx_freq": 155.55,
                "band": "VHF",
                "mode": "FM",
            }
        raise AssertionError(f"Unexpected GET {path}")

    def patch(self, path, *, json=None, params=None):
        entry_id = int(path.rsplit("/", 1)[-1])
        row = self.entries[entry_id]
        row.update(json or {})
        self.audit.setdefault(entry_id, []).append({"action": "update", "changed_by": row.get("operator_user_id")})
        return dict(row)

    def delete(self, path, *, params=None):
        entry_id = int(path.rsplit("/", 1)[-1])
        self.entries.pop(entry_id, None)


@pytest.fixture()
def fake_client(monkeypatch):
    fake = FakeApiClient()
    monkeypatch.setattr("utils.api_client.api_client", fake)
    AppState.set_active_incident("test-incident")
    AppState.set_active_user_id("comm_op")
    return fake


def test_repository_creates_entry_and_audit(fake_client):
    repo = ApiCommsLogRepository(incident_id="test-incident")
    entry = CommsLogEntry(
        message="Rescue team checking in",
        priority="Routine",
        resource_id=1,
        resource_label="VHF-1",
        from_unit="Team 1",
        to_unit="Base",
    )
    created = repo.add_entry(entry)
    assert created.id is not None
    assert created.resource_label == "VHF-1"

    updated = repo.update_entry(created.id, {"message": "Updated message", "follow_up_required": True})
    assert updated.message == "Updated message"
    assert updated.follow_up_required is True

    audits = repo.list_audit_entries(created.id)
    assert len(audits) >= 2
    assert audits[0].action in {"update", "create"}

    results = repo.list_entries(CommsLogQuery(priorities=["Routine"]))
    assert results and results[0].message == "Updated message"


def test_service_exports_csv(tmp_path, fake_client):
    repo = ApiCommsLogRepository(incident_id="test-incident")
    service = CommsLogService(repository=repo)
    service.create_entry(
        {
            "message": "Perimeter established",
            "priority": "Priority",
            "resource_id": 1,
            "resource_label": "VHF-1",
            "from_unit": "Base",
            "to_unit": "Ops",
            "follow_up_required": False,
        }
    )
    export_path = tmp_path / "log.csv"
    service.export_to_csv(export_path, CommsLogQuery())
    assert export_path.exists()
    text = export_path.read_text(encoding="utf-8")
    assert "Perimeter established" in text
