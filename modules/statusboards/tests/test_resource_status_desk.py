from __future__ import annotations

from modules.statusboards.resource_status_desk import ResourceStatusDesk
from utils import incident_context
from utils.api_client import api_client


class _Signal:
    def __init__(self) -> None:
        self.emitted: list[list[dict]] = []

    def emit(self, rows: list[dict]) -> None:
        self.emitted.append(rows)


class _DeskHarness:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self._rows: list[dict] = []
        self.resource_rows_changed = _Signal()

    def _backfill_resource_ids(self) -> None:
        self.calls.append("backfill")

    def _fetch_resource_status_docs(self) -> list[dict]:
        self.calls.append("fetch")
        return [
            {
                "id": "rs-1",
                "entity_type": "personnel",
                "record_id": 186,
                "resource_id": "405021",
                "resource_name": "Brendan Pheley",
                "resource_type": "Personnel",
                "status": "Assigned",
            }
        ]

    def _doc_to_row(self, doc: dict) -> dict:
        self.calls.append("map")
        return dict(doc)


def test_rebuild_backfills_resource_ids_before_rendering_rows() -> None:
    desk = _DeskHarness()

    ResourceStatusDesk._rebuild(desk)  # type: ignore[arg-type]

    assert desk.calls == ["backfill", "fetch", "map"]
    assert desk._rows[0]["resource_id"] == "405021"
    assert desk.resource_rows_changed.emitted == [desk._rows]


class _TeamSyncHarness:
    def _fetch_team_docs(self) -> list[dict]:
        return [
            {
                "name": "Air Team",
                "status": "Available",
                "aircraft_json": '["33"]',
            }
        ]

    def _fetch_resource_status_docs(self) -> list[dict]:
        return [
            {
                "id": "rs-air",
                "entity_type": "aircraft",
                "record_id": 33,
                "resource_id": "N296CP",
                "resource_name": "CAP 296",
                "resource_type": "Aircraft",
                "status": "Available",
            }
        ]


def test_team_sync_advances_existing_available_aircraft_to_assigned(monkeypatch) -> None:
    patch_calls: list[tuple[str, dict]] = []
    post_calls: list[tuple[str, dict]] = []

    def fake_get(path: str):
        assert path == "/api/master/aircraft/33"
        return {"aircraft_id": "N296CP", "callsign": "CAP 296"}

    def fake_patch(path: str, json: dict):
        patch_calls.append((path, json))
        return {}

    def fake_post(path: str, json: dict):
        post_calls.append((path, json))
        return {}

    monkeypatch.setattr(incident_context, "get_active_incident_id", lambda: "incident-1")
    monkeypatch.setattr(api_client, "get", fake_get)
    monkeypatch.setattr(api_client, "patch", fake_patch)
    monkeypatch.setattr(api_client, "post", fake_post)

    ResourceStatusDesk._do_sync_team_members(_TeamSyncHarness())  # type: ignore[arg-type]

    assert post_calls == []
    assert patch_calls == [
        (
            "/api/incidents/incident-1/resource-status/rs-air",
            {"assigned_to": "Air Team"},
        ),
        (
            "/api/incidents/incident-1/resource-status/rs-air/status",
            {"status": "Assigned", "changed_by": "Desk Sync"},
        ),
    ]
