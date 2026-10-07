"""Export/import round-trip coverage for the `master_link` field.

A document's `master_id` only means something on the server it was copied
from. These tests confirm that importing an incident re-resolves the link
when it demonstrably still matches this server's own master DB, and marks
it "orphaned" otherwise, rather than silently keeping a dangling foreign
reference (see Design Documents/Instructions/mongodb_schema_decisions.md).
"""
from __future__ import annotations

import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db, get_system_db, get_incident_db_name
from sarapp_db.mongo.master_link import LINKED, ORPHANED, build_master_link
from sarapp_db.mongo.mongo_client import get_client
from sarapp_db.mongo.server_identity import get_server_id


def _drop(incident_id: str) -> None:
    get_client().drop_database(get_incident_db_name(incident_id))


def _make_incident(client, number: str) -> str:
    created = client.post(
        "/api/incidents",
        json={"number": number, "name": number, "type": "SAR"},
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


def test_master_link_still_resolves_on_same_server_import():
    this_server = get_server_id()
    master_col = get_master_db()["personnel"]
    master_col.delete_many({"_id": "TEST-MASTER-LINK-PERSON"})
    master_col.insert_one({"_id": "TEST-MASTER-LINK-PERSON", "person_record": 999001, "name": "Test Person"})

    app = create_app()
    with TestClient(app) as client:
        source_id = _make_incident(client, "TEST-MLINK-SRC-1")
        try:
            db = get_incident_db(source_id)
            db["incident_personnel"].insert_one({
                "person_record": 999001,
                "incident_id": source_id,
                "name": "Test Person",
                "master_link": build_master_link(
                    master_collection="personnel",
                    master_id="TEST-MASTER-LINK-PERSON",
                    master_server_origin=this_server,
                ),
            })

            exported = client.get(f"/api/incidents/{source_id}/export")
            assert exported.status_code == 200

            imported = client.post(
                "/api/incidents/import",
                data={"number": "TEST-MLINK-DST-1", "name": "Import Target"},
                files={"file": ("export.zip", exported.content, "application/zip")},
            )
            assert imported.status_code == 201, imported.text
            target_id = imported.json()["id"]
            try:
                target_doc = get_incident_db(target_id)["incident_personnel"].find_one({"person_record": 999001})
                assert target_doc["master_link"]["sync_state"] == LINKED
                assert target_doc["master_link"]["master_id"] == "TEST-MASTER-LINK-PERSON"
            finally:
                _drop(target_id)
                get_system_db()["incidents"].delete_many({"_id": target_id})
        finally:
            _drop(source_id)
            get_system_db()["incidents"].delete_many({"_id": source_id})
            master_col.delete_many({"_id": "TEST-MASTER-LINK-PERSON"})


def test_master_link_orphaned_when_origin_server_unresolvable():
    app = create_app()
    with TestClient(app) as client:
        source_id = _make_incident(client, "TEST-MLINK-SRC-2")
        try:
            db = get_incident_db(source_id)
            db["incident_personnel"].insert_one({
                "person_record": 999002,
                "incident_id": source_id,
                "name": "Foreign Person",
                "master_link": build_master_link(
                    master_collection="personnel",
                    master_id="SOME-OTHER-SERVERS-UUID",
                    master_server_origin="some-other-server-entirely",
                ),
            })

            exported = client.get(f"/api/incidents/{source_id}/export")
            assert exported.status_code == 200

            imported = client.post(
                "/api/incidents/import",
                data={"number": "TEST-MLINK-DST-2", "name": "Import Target"},
                files={"file": ("export.zip", exported.content, "application/zip")},
            )
            assert imported.status_code == 201, imported.text
            target_id = imported.json()["id"]
            try:
                target_doc = get_incident_db(target_id)["incident_personnel"].find_one({"person_record": 999002})
                assert target_doc["master_link"]["sync_state"] == ORPHANED
            finally:
                _drop(target_id)
                get_system_db()["incidents"].delete_many({"_id": target_id})
        finally:
            _drop(source_id)
            get_system_db()["incidents"].delete_many({"_id": source_id})
