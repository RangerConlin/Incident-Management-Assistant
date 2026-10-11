"""End-to-end coverage of the sync relay: a simulated "local server" (its
own local master collection, driven through BaseRepository exactly like a
real LAN server would) talking to a real central FastAPI app
(`create_app(mode="master_only")`) over an in-process ASGI transport —
no real network, no real uvicorn process, but the same push/pull/outbox
code paths production uses.
"""
from __future__ import annotations

import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

import pytest
from starlette.testclient import TestClient

from sarapp_db import sync as sync_package  # noqa: F401 - ensures package import works
from sarapp_db.mongo import repository as repository_module
from sarapp_db.mongo.mongo_client import get_client
from sarapp_db.mongo.repository import BaseRepository
from sarapp_db.sync import central_client, checkpoint, config, outbox
from sarapp_db.sync.loop import drain_outbox, pull_and_apply

LOCAL_DB_NAME = "TEST_SYNC_LOCAL_MASTER"
CENTRAL_DB_NAME = "TEST_SYNC_CENTRAL_MASTER"
CENTRAL_URL = "http://central-master.test"
TOKEN = "test-sync-token"


class _LocalPersonnelRepository(BaseRepository):
    collection_name = "personnel"
    soft_deletes = False


class _LocalEquipmentRepository(BaseRepository):
    collection_name = "equipment"
    soft_deletes = False


class _LocalVehicleRepository(BaseRepository):
    collection_name = "vehicles"
    soft_deletes = False


class _LocalMeetingTemplatesRepository(BaseRepository):
    collection_name = "meeting_templates"
    soft_deletes = False


class _AlwaysFailsTransport:
    """Stand-in transport simulating "central unreachable" — any request
    raises, like a real connection failure would."""

    def handle_request(self, request):  # noqa: ANN001 - matches httpx transport protocol
        import httpx

        raise httpx.ConnectError("simulated unreachable central database")

    def close(self) -> None:
        pass


def _central_app():
    from sarapp_db.api.app import create_app

    return create_app(mode="master_only")


def _local_db():
    return get_client()[LOCAL_DB_NAME]


def _central_db():
    return get_client()[CENTRAL_DB_NAME]


def _system_db():
    from sarapp_db.mongo.database_manager import get_system_db

    return get_system_db()


@pytest.fixture
def sync_env(monkeypatch):
    """Wire the local-master-db check, env config, and the ASGI test
    transport so push/pull hit a real in-process central app."""
    monkeypatch.setattr(repository_module, "_LOCAL_MASTER_DB_NAME", LOCAL_DB_NAME)
    monkeypatch.setenv("SARAPP_CLOUD_ROUTER_TOKEN", TOKEN)
    monkeypatch.setenv("SARAPP_CENTRAL_MASTER_URL", CENTRAL_URL)
    monkeypatch.setenv("SARAPP_MASTER_DB_NAME", CENTRAL_DB_NAME)

    # TestClient's own transport is already a sync-compatible ASGI bridge
    # (it runs the app in a background event loop under the hood) — reuse
    # it directly instead of httpx.ASGITransport, which in this httpx
    # version only implements the async request path.
    transport = TestClient(_central_app())._transport
    monkeypatch.setattr(central_client, "_test_transport", transport)

    get_client().drop_database(LOCAL_DB_NAME)
    get_client().drop_database(CENTRAL_DB_NAME)
    _system_db()["sync_state"].delete_many({})
    _system_db()["sync_pull_checkpoints"].delete_many({})
    yield
    get_client().drop_database(LOCAL_DB_NAME)
    get_client().drop_database(CENTRAL_DB_NAME)
    _system_db()["sync_state"].delete_many({})
    _system_db()["sync_pull_checkpoints"].delete_many({})


def test_local_write_relays_immediately_to_central(sync_env):
    repo = _LocalPersonnelRepository(_local_db())

    saved = repo.insert_one({"name": "Alice", "person_record": 1})

    central_doc = _central_db()["personnel"].find_one({"_id": saved["_id"]})
    assert central_doc is not None
    assert central_doc["name"] == "Alice"
    # Nothing should be queued — the push succeeded immediately.
    assert outbox.list_pending(_system_db()) == []


def test_local_write_relays_for_a_second_syncable_collection(sync_env):
    """Proves SYNCABLE_MASTER_COLLECTIONS is a real extension point, not
    something only ever exercised for personnel — equipment uses the exact
    same relay/outbox/pull code paths with zero collection-specific code."""
    repo = _LocalEquipmentRepository(_local_db())

    saved = repo.insert_one({"name": "Radio Kit 7", "equipment_record": 1})

    central_doc = _central_db()["equipment"].find_one({"_id": saved["_id"]})
    assert central_doc is not None
    assert central_doc["name"] == "Radio Kit 7"
    assert outbox.list_pending(_system_db()) == []


def test_failed_push_is_queued_then_drained_on_retry(sync_env, monkeypatch):
    repo = _LocalPersonnelRepository(_local_db())

    # Swap in a transport that always raises, simulating "central
    # unreachable" (a real network failure, not an app-level rejection).
    monkeypatch.setattr(central_client, "_test_transport", _AlwaysFailsTransport())
    saved = repo.insert_one({"name": "Bob", "person_record": 2})

    assert _central_db()["personnel"].find_one({"_id": saved["_id"]}) is None
    pending = outbox.list_pending(_system_db())
    assert len(pending) == 1
    assert pending[0]["doc_id"] == saved["_id"]

    # Restore the working transport and drain — the queued write should now
    # go through.
    monkeypatch.setattr(central_client, "_test_transport", TestClient(_central_app())._transport)
    drain_outbox(local_master_db=_local_db())

    assert _central_db()["personnel"].find_one({"_id": saved["_id"]})["name"] == "Bob"
    assert outbox.list_pending(_system_db()) == []


def test_pull_and_apply_downloads_central_only_changes(sync_env):
    # A record that exists centrally but never originated on this server
    # (e.g. created through the central web GUI, or by another server).
    _central_db()["personnel"].insert_one(
        {"_id": "central-only-1", "name": "Carol", "updated_at": "2026-01-01T00:00:00"}
    )

    pull_and_apply("personnel", local_master_db=_local_db())

    local_doc = _local_db()["personnel"].find_one({"_id": "central-only-1"})
    assert local_doc is not None
    assert local_doc["name"] == "Carol"
    assert checkpoint.get_last_pulled_at(_system_db(), "personnel") == "2026-01-01T00:00:00"

    # A second pull with nothing new centrally must not re-fetch/re-apply
    # (checkpoint already caught up).
    pull_and_apply("personnel", local_master_db=_local_db())
    assert checkpoint.get_last_pulled_at(_system_db(), "personnel") == "2026-01-01T00:00:00"


def test_local_write_relays_for_a_slug_keyed_collection(sync_env):
    """meeting_templates has no dual key — it's keyed by a user-chosen slug
    with upsert semantics, not an auto-incrementing id (see
    mongodb_schema_decisions.md "Personnel: central-vs-local record ids").
    It still needs the ordinary push/pull relay, same as any other
    SYNCABLE_MASTER_COLLECTIONS entry, just with no master-field minting."""
    repo = _LocalMeetingTemplatesRepository(_local_db())

    saved = repo.insert_one({"slug": "safety-briefing", "name": "Safety Briefing"})

    central_doc = _central_db()["meeting_templates"].find_one({"_id": saved["_id"]})
    assert central_doc is not None
    assert central_doc["slug"] == "safety-briefing"
    assert "slug_master" not in central_doc


def test_push_assigns_equipment_record_master_once(sync_env):
    """Same dual-key pattern as personnel, generalized in sync.py's
    _DUAL_KEY_MASTER_FIELDS — proves it isn't personnel-specific code."""
    repo = _LocalEquipmentRepository(_local_db())
    saved = repo.insert_one({"name": "Radio Kit 11", "equipment_record": 4})
    assert saved.get("equipment_record_master") is None

    central_doc = _central_db()["equipment"].find_one({"_id": saved["_id"]})
    assert central_doc is not None
    assert isinstance(central_doc["equipment_record_master"], int)


def test_vehicle_router_writes_relay_to_central(sync_env, monkeypatch):
    """Vehicle API writes must go through BaseRepository like personnel and
    equipment, otherwise local vehicle edits bypass the central-sync outbox.
    """
    from sarapp_db.api.routers import vehicles as vehicles_router

    monkeypatch.setattr(vehicles_router, "get_master_db", _local_db)

    saved = vehicles_router.create_vehicle(
        vehicles_router.VehicleBody(
            vehicle_id="Unit 12",
            make="Ford",
            model="F-150",
            status_id="Available",
        )
    )

    central_doc = _central_db()["vehicles"].find_one({"vehicle_id": "Unit 12"})
    assert central_doc is not None
    assert central_doc["make"] == "Ford"
    assert isinstance(saved["vehicle_record"], int)
    assert saved.get("vehicle_record_master") is None
    assert isinstance(central_doc["vehicle_record_master"], int)
    assert "vehicle_record" not in central_doc
    assert outbox.list_pending(_system_db()) == []


def test_vehicle_hard_delete_relays_as_tombstone(sync_env):
    repo = _LocalVehicleRepository(_local_db())
    saved = repo.insert_one({"vehicle_id": "Unit 13", "vehicle_record": 1})
    assert _central_db()["vehicles"].find_one({"_id": saved["_id"]}) is not None

    repo.delete_one(saved["_id"])

    assert _central_db()["vehicles"].find_one({"_id": saved["_id"]}) is None
    assert _central_db()["sync_tombstones"].find_one({"collection": "vehicles", "doc_id": saved["_id"]}) is not None


def test_pull_serializes_legacy_vehicle_object_ids(sync_env):
    """Vehicle rows created by the old raw-Mongo router can have ObjectId
    primary keys. The central pull API must JSON-sanitize them instead of
    failing the whole vehicle pull with a 500.
    """
    _central_db()["vehicles"].insert_one(
        {
            "vehicle_id": "Legacy Unit 14",
            "vehicle_record_master": 14,
            "make": "Ford",
            "updated_at": "2026-01-03T00:00:00",
        }
    )

    assert pull_and_apply("vehicles", local_master_db=_local_db()) is True

    pulled = _local_db()["vehicles"].find_one({"vehicle_id": "Legacy Unit 14"})
    assert pulled is not None
    assert isinstance(pulled["_id"], str)
    assert pulled["vehicle_record_master"] == 14
    assert pulled["vehicle_record"] == 1


def test_central_pull_serializes_legacy_object_ids_for_every_syncable_catalog(sync_env):
    app = _central_app()
    headers = {"x-sarapp-sync-token": TOKEN}

    for collection in config.SYNCABLE_MASTER_COLLECTIONS:
        _central_db()[collection].delete_many({"legacy_probe": True})
        doc = {
            "legacy_probe": True,
            "name": f"Legacy {collection}",
            "updated_at": "2026-01-04T00:00:00",
        }
        fields = config.DUAL_KEY_RECORD_FIELDS.get(collection)
        if fields is not None:
            _local_field, master_field = fields
            doc[master_field] = 9001
        if collection == "meeting_templates":
            doc["slug"] = "legacy-probe"
        _central_db()[collection].insert_one(doc)

        try:
            with TestClient(app) as client:
                response = client.get(
                    "/api/sync/pull",
                    params={"collection": collection, "since": ""},
                    headers=headers,
                )

            assert response.status_code == 200, collection
            docs = [item for item in response.json()["docs"] if item.get("legacy_probe") is True]
            assert docs, collection
            assert isinstance(docs[0]["_id"], str)
        finally:
            _central_db()[collection].delete_many({"legacy_probe": True})


def test_objective_template_router_writes_relay_to_central(sync_env, monkeypatch):
    from sarapp_db.api.routers import objective_templates

    monkeypatch.setattr(objective_templates, "get_master_db", _local_db)

    saved = objective_templates.create_objective_template(
        {
            "code": "OBJ-1",
            "title": "Search Area A",
            "description": "Search the assigned area.",
            "tags": ["search"],
        }
    )

    central_doc = _central_db()["objective_templates"].find_one({"title": "Search Area A"})
    assert central_doc is not None
    assert saved.get("int_id_master") is None
    assert isinstance(central_doc["int_id_master"], int)
    assert "int_id" not in central_doc
    assert outbox.list_pending(_system_db()) == []


def test_strategy_template_router_writes_relay_to_central(sync_env, monkeypatch):
    from sarapp_db.api.routers import strategy_templates

    monkeypatch.setattr(strategy_templates, "get_master_db", _local_db)

    saved = strategy_templates.create_strategy_template(
        {
            "objective_template_id": 1,
            "title": "Grid Search",
            "description": "Run a grid search.",
            "tags": ["search"],
        }
    )

    central_doc = _central_db()["strategy_templates"].find_one({"title": "Grid Search"})
    assert central_doc is not None
    assert saved.get("int_id_master") is None
    assert isinstance(central_doc["int_id_master"], int)
    assert "int_id" not in central_doc
    assert outbox.list_pending(_system_db()) == []


def test_local_hard_delete_relays_as_tombstone_and_a_second_pull_removes_it_elsewhere(sync_env):
    """equipment.delete_equipment hard-deletes locally. That delete must
    still reach the central database (as a tombstone, since a literal
    removal there would be invisible to a later "what changed since X"
    pull by some other server) and, from there, a pull must remove the
    record from a third location too — simulating another server that
    also has a local copy."""
    repo = _LocalEquipmentRepository(_local_db())
    saved = repo.insert_one({"name": "Radio Kit 9", "equipment_record": 2})
    assert _central_db()["equipment"].find_one({"_id": saved["_id"]}) is not None

    # A third location standing in for "another server's local sarapp_master"
    # that already pulled this record before the delete happened.
    other_server_db_name = "TEST_SYNC_OTHER_SERVER_MASTER"
    get_client().drop_database(other_server_db_name)
    other_server_db = get_client()[other_server_db_name]
    other_server_db["equipment"].insert_one(dict(saved))

    repo.delete_one(saved["_id"])

    assert _local_db()["equipment"].find_one({"_id": saved["_id"]}) is None
    # The real central document is genuinely gone too — a tombstone is
    # tracked separately (sync_tombstones), not as a lingering flag on the
    # record itself, so central's own reads see a clean deletion.
    assert _central_db()["equipment"].find_one({"_id": saved["_id"]}) is None
    assert _central_db()["sync_tombstones"].find_one({"doc_id": saved["_id"]}) is not None

    try:
        pull_and_apply("equipment", local_master_db=other_server_db)
        assert other_server_db["equipment"].find_one({"_id": saved["_id"]}) is None
    finally:
        get_client().drop_database(other_server_db_name)


def test_failed_delete_is_queued_then_drained_on_retry(sync_env, monkeypatch):
    repo = _LocalEquipmentRepository(_local_db())
    saved = repo.insert_one({"name": "Radio Kit 10", "equipment_record": 3})
    assert _central_db()["equipment"].find_one({"_id": saved["_id"]}) is not None

    monkeypatch.setattr(central_client, "_test_transport", _AlwaysFailsTransport())
    repo.delete_one(saved["_id"])

    # Still present centrally — the delete push failed and should have
    # queued instead.
    assert _central_db()["equipment"].find_one({"_id": saved["_id"]}) is not None
    pending = outbox.list_pending(_system_db())
    assert len(pending) == 1
    assert pending[0]["op"] == "delete"
    assert pending[0]["doc_id"] == saved["_id"]

    monkeypatch.setattr(central_client, "_test_transport", TestClient(_central_app())._transport)
    drain_outbox(local_master_db=_local_db())

    assert _central_db()["equipment"].find_one({"_id": saved["_id"]}) is None
    assert _central_db()["sync_tombstones"].find_one({"doc_id": saved["_id"]}) is not None
    assert outbox.list_pending(_system_db()) == []


def test_push_assigns_person_record_master_once_and_pull_propagates_it(sync_env):
    """A personnel record created offline has no person_record_master (see
    personnel_schema.py) — only the central catalog ever mints one, the
    first time it sees the record. That assignment must then flow back out
    to any other server that pulls the record afterward."""
    repo = _LocalPersonnelRepository(_local_db())
    saved = repo.insert_one({"name": "Dana", "person_record": 7})
    assert saved.get("person_record_master") is None

    central_doc = _central_db()["personnel"].find_one({"_id": saved["_id"]})
    assert central_doc is not None
    assigned = central_doc["person_record_master"]
    assert isinstance(assigned, int)
    assert "person_record" not in central_doc

    # Pushing the exact same unchanged document again must not mint a
    # second id — the field is already set, so apply_incoming treats it as
    # skipped_same_or_older and the mint helper is never reached.
    second_push = central_client.push_one(
        config.central_master_url(), config.sync_token(), collection="personnel", doc=saved
    )
    assert second_push is True
    central_doc = _central_db()["personnel"].find_one({"_id": saved["_id"]})
    assert central_doc["person_record_master"] == assigned
    assert "person_record" not in central_doc

    other_server_db_name = "TEST_SYNC_OTHER_SERVER_MASTER_PERSONNEL"
    get_client().drop_database(other_server_db_name)
    other_server_db = get_client()[other_server_db_name]
    try:
        pull_and_apply("personnel", local_master_db=other_server_db)
        pulled = other_server_db["personnel"].find_one({"_id": saved["_id"]})
        assert pulled is not None
        assert pulled["person_record_master"] == assigned
        # person_record is server-local. The receiving server gets its own
        # local id while preserving the central agency id.
        assert pulled["person_record"] == 1
    finally:
        get_client().drop_database(other_server_db_name)


def test_pull_reassigns_server_local_record_id_when_central_doc_has_foreign_local_id(sync_env):
    """Regression for demo-server resync failure:
    central used to echo `person_record` from one server back to another.
    Since person_record is unique only within one local catalog, that caused
    duplicate-key failures on the receiving server.
    """
    local_db = _local_db()
    local_db["personnel"].insert_one(
        {
            "_id": "already-local",
            "name": "Existing Local Person",
            "person_record": 1,
            "updated_at": "2026-01-01T00:00:00",
        }
    )
    _central_db()["personnel"].insert_one(
        {
            "_id": "central-person",
            "name": "Central Person",
            "person_record": 1,
            "person_record_master": 99,
            "updated_at": "2026-01-02T00:00:00",
        }
    )

    pull_and_apply("personnel", local_master_db=local_db)

    pulled = local_db["personnel"].find_one({"_id": "central-person"})
    assert pulled is not None
    assert pulled["person_record_master"] == 99
    assert pulled["person_record"] == 2


def test_push_rejected_for_non_syncable_collection(sync_env):
    # organizations is a "lockdown" collection (see mongodb_schema_decisions.md)
    # — central-authoritative, never pushed from a local catalog — so it's
    # guaranteed to stay out of SYNCABLE_MASTER_COLLECTIONS, unlike
    # hazard_types/gar_templates/etc., which have since been added.
    sent = central_client.push_one(
        config.central_master_url(),
        config.sync_token(),
        collection="organizations",
        doc={"_id": "x", "updated_at": "2026-01-01T00:00:00"},
    )
    assert sent is False
