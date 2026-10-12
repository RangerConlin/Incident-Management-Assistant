"""Round-trip test for the universal incident export/import package.

Exports a real incident (collections + a GridFS attachment) from one
database and imports it back as a brand-new incident, then checks the
restored data and attachment bytes match the original.
"""
from __future__ import annotations

import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_incident_db, get_system_db, get_incident_db_name
from sarapp_db.mongo.mongo_client import get_client


def _drop(incident_id: str) -> None:
    get_client().drop_database(get_incident_db_name(incident_id))


def test_export_then_import_round_trips_data_and_attachment():
    app = create_app()
    with TestClient(app) as client:
        created = client.post(
            "/api/incidents",
            json={"number": "TEST-XPORT-SRC", "name": "Export Source", "type": "SAR"},
        )
        assert created.status_code == 201, created.text
        source_id = created.json()["id"]

        try:
            db = get_incident_db(source_id)
            db["teams"].insert_one({"int_id": 1, "name": "Team 1", "status": "Available"})
            db["tasks"].insert_one({"int_id": 1, "task_id": "T-001", "title": "Search Sector 1"})

            uploaded = client.post(
                f"/api/incidents/{source_id}/attachments",
                data={"owner_type": "task", "owner_id": "1"},
                files={"file": ("photo.jpg", b"fake jpeg bytes", "image/jpeg")},
            )
            assert uploaded.status_code == 201, uploaded.text

            exported = client.get(f"/api/incidents/{source_id}/export")
            assert exported.status_code == 200
            assert exported.headers["content-type"] == "application/zip"

            imported = client.post(
                "/api/incidents/import",
                data={"number": "TEST-XPORT-DST", "name": "Import Target"},
                files={"file": ("export.zip", exported.content, "application/zip")},
            )
            assert imported.status_code == 201, imported.text
            target_id = imported.json()["id"]

            try:
                target_db = get_incident_db(target_id)
                teams = list(target_db["teams"].find({}))
                assert len(teams) == 1
                assert teams[0]["name"] == "Team 1"
                assert teams[0]["_id"] == db["teams"].find_one({})["_id"]

                tasks = list(target_db["tasks"].find({}))
                assert len(tasks) == 1
                assert tasks[0]["task_id"] == "T-001"

                target_attachments = client.get(f"/api/incidents/{target_id}/attachments").json()
                assert len(target_attachments) == 1
                attachment_id = target_attachments[0]["attachment_id"]

                downloaded = client.get(f"/api/incidents/{target_id}/attachments/{attachment_id}/download")
                assert downloaded.status_code == 200
                assert downloaded.content == b"fake jpeg bytes"
            finally:
                _drop(target_id)
                get_system_db()["incidents"].delete_many({"_id": target_id})
        finally:
            _drop(source_id)
            get_system_db()["incidents"].delete_many({"_id": source_id})
