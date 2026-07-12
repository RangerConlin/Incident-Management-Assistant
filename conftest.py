"""Repository-wide pytest configuration."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_INCIDENT_DB_PREFIX = "sarapp_incident_"
_MONGO_URI_ENV = "SARAPP_MONGO_URI"
_DEFAULT_MONGO_URI = "mongodb://localhost:27017"

_BASELINE_INCIDENT_DBS: set[str] = set()
_BASELINE_INCIDENT_REGISTRY_IDS: set[str] = set()

_KNOWN_TEST_INCIDENT_IDS = {
    "1001",
    "2001",
    "2002",
    "FIN-TEST-001",
    "INC-2",
    "INC-3",
    "INC-FAC-1",
    "INC-LOC-LINK-1",
    "INC-OPS-001",
    "SMOKE_TEST",
    "TEST-1",
    "TEST-123",
    "TEST-INC",
    "TESTCACHE1",
    "TESTCACHE_LIMITS",
    "TESTLISTENER1",
    "TESTLISTENER2",
    "TESTWEATHER1",
    "TESTWEATHER2",
    "TEST_CHECKIN_TEAMS_INT_ID",
    "TEST_COMMS_CONTACTS",
    "TEST_COMMS_CONTACTS_INT_ID",
    "TEST_IC_OVERVIEW",
    "TEST_SAFETY_HAZARDS",
    "UI-INC",
    "dev_framework_check",
    "ics214-test",
    "ics214-test2",
    "incident",
    "m1",
    "resource-request-test",
    "resource-status-test",
    "ui-sanity-test",
    "x",
}

_TEST_INCIDENT_PREFIXES = (
    "TEST",
    "FIN-TEST",
    "SMOKE_TEST",
    "resource-",
    "ui-sanity-test",
    "ics214-test",
)


def _mongo_client():
    try:
        from pymongo import MongoClient
    except Exception:
        return None

    uri = os.environ.get(_MONGO_URI_ENV, "").strip() or _DEFAULT_MONGO_URI
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=500)
        client.admin.command("ping")
        return client
    except Exception:
        return None


def _incident_id_from_db_name(db_name: str) -> str:
    return db_name[len(_INCIDENT_DB_PREFIX):]


def _is_known_test_incident_id(incident_id: str) -> bool:
    return (
        incident_id in _KNOWN_TEST_INCIDENT_IDS
        or any(incident_id.startswith(prefix) for prefix in _TEST_INCIDENT_PREFIXES)
    )


def _incident_db_names(client) -> set[str]:
    return {
        name
        for name in client.list_database_names()
        if name.startswith(_INCIDENT_DB_PREFIX)
    }


def _registry_incident_ids(client) -> set[str]:
    return {
        str(doc.get("incident_id") or "")
        for doc in client.sarapp_system.incidents.find({}, {"incident_id": 1})
        if doc.get("incident_id")
    }


def _cleanup_test_mongo_state(client, *, include_new: bool) -> None:
    current_dbs = _incident_db_names(client)
    for db_name in sorted(current_dbs):
        incident_id = _incident_id_from_db_name(db_name)
        is_new = db_name not in _BASELINE_INCIDENT_DBS
        if _is_known_test_incident_id(incident_id) or (include_new and is_new):
            client.drop_database(db_name)

    registry_ids = _registry_incident_ids(client)
    stale_registry_ids = {
        incident_id
        for incident_id in registry_ids
        if _is_known_test_incident_id(incident_id)
        or (include_new and incident_id not in _BASELINE_INCIDENT_REGISTRY_IDS)
    }
    if stale_registry_ids:
        client.sarapp_system.incidents.delete_many(
            {"incident_id": {"$in": sorted(stale_registry_ids)}}
        )


def pytest_sessionstart(session) -> None:  # noqa: ARG001 - pytest hook signature
    """Keep Mongo-backed tests from leaving incident databases behind."""
    client = _mongo_client()
    if client is None:
        return

    global _BASELINE_INCIDENT_DBS, _BASELINE_INCIDENT_REGISTRY_IDS
    _BASELINE_INCIDENT_DBS = _incident_db_names(client)
    _BASELINE_INCIDENT_REGISTRY_IDS = _registry_incident_ids(client)
    _cleanup_test_mongo_state(client, include_new=False)
    _BASELINE_INCIDENT_DBS = _incident_db_names(client)
    _BASELINE_INCIDENT_REGISTRY_IDS = _registry_incident_ids(client)


def pytest_sessionfinish(session, exitstatus) -> None:  # noqa: ARG001 - pytest hook signature
    """Drop test-created incident databases and registry rows after pytest."""
    client = _mongo_client()
    if client is None:
        return
    _cleanup_test_mongo_state(client, include_new=True)


@pytest.fixture(autouse=True)
def _stop_incident_cache_ws_after_test():
    """Tear down any IncidentCache WebSocket client a test left running.

    Any test that calls AppState.set_active_incident(...) starts a background
    IncidentWebSocketClient thread via utils.incident_cache_loader. That thread
    retries its connection every few seconds forever; stop it after every test
    regardless of whether the test imported incident_cache_loader itself.
    """
    yield
    from utils import incident_cache_loader

    incident_cache_loader.activate_incident(None)
