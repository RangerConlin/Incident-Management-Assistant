from __future__ import annotations

import pytest

from modules.communications.traffic_log.services import CommsLogService
from utils.api_client import api_client
from utils.catalog_cache import catalog_cache
from utils.incident_cache import incident_cache
from utils.state import AppState


@pytest.fixture(autouse=True)
def _clear_caches():
    incident_cache.clear()
    catalog_cache.invalidate()
    yield
    incident_cache.clear()
    catalog_cache.invalidate()


class _Repo:
    def __init__(self, incident_id: str) -> None:
        self.incident_id = incident_id


def test_list_channels_reads_from_cache(monkeypatch):
    monkeypatch.setattr(AppState, "get_active_incident", staticmethod(lambda: "INC-CACHE"))
    monkeypatch.setattr(
        api_client, "get",
        lambda path, params=None: [{"id": 1, "name": "Command 1", "function": "Command"}],
    )

    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "incident_channels": [
                {"_id": "c-1", "channel_id": "INC-CACHE-CH-2", "master_id": "1", "sort_index": 1},
            ]
        },
    )

    service = CommsLogService(repository=_Repo("INC-CACHE"))
    channels = service.list_channels()

    assert channels == [
        {"id": 2, "channel_name": "Command 1", "name": "Command 1", "function": "Command"}
    ]


def test_list_channels_falls_back_to_channels_plan_api_without_cache(monkeypatch):
    calls: list[str] = []

    def fake_get(path, params=None):
        calls.append(path)
        return [{"id": 3, "channel": "Tac 1", "function": "Tactical"}]

    monkeypatch.setattr(api_client, "get", fake_get)

    service = CommsLogService(repository=_Repo("INC-NO-CACHE"))
    channels = service.list_channels()

    assert calls == ["/api/incidents/INC-NO-CACHE/channels-plan"]
    assert channels == [
        {"id": 3, "channel_name": "Tac 1", "name": "Tac 1", "function": "Tactical"}
    ]
