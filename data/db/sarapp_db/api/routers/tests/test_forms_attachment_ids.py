from __future__ import annotations

import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db


INCIDENT_ID = "TEST_FORMS_ATTACHMENTS"


def _clear(db) -> None:
    db[IncidentCollections.FORMS].delete_many({})
    db[IncidentCollections.ATTACHMENTS].delete_many({})


def _seed_form(db) -> None:
    db[IncidentCollections.FORMS].insert_one(
        {
            "instance_id": f"{INCIDENT_ID}-FORM-1",
            "incident_id": INCIDENT_ID,
            "family_id": 1,
            "template_id": 1,
            "template_version_id": 1,
            "title": "ICS 214",
            "agency": "FEMA",
            "status": "draft",
            "revision_number": 1,
            "attachment_ids": [],
            "metadata": {},
            "values": {},
            "deleted": False,
        }
    )


def _seed_attachment(db, *, attachment_id: str, owner_id: str, owner_type: str = "form") -> None:
    db[IncidentCollections.ATTACHMENTS].insert_one(
        {
            "int_id": int(attachment_id.rsplit("-", 1)[-1]),
            "attachment_id": attachment_id,
            "incident_id": INCIDENT_ID,
            "owner_type": owner_type,
            "owner_id": owner_id,
            "category": "form-export",
            "filename": "ics214.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 100,
            "checksum_sha256": "abc123",
            "gridfs_file_id": "gridfs-1",
            "deleted": False,
        }
    )


def test_form_attachment_ids_round_trip():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    _seed_form(db)
    _seed_attachment(db, attachment_id=f"{INCIDENT_ID}-ATT-1", owner_id=f"{INCIDENT_ID}-FORM-1")

    app = create_app()
    with TestClient(app) as client:
        added = client.post(
            f"/api/incidents/{INCIDENT_ID}/forms/1/attachments",
            json={"attachment_id": f"{INCIDENT_ID}-ATT-1"},
        )
        assert added.status_code == 200, added.text
        assert added.json()["attachment_ids"] == [f"{INCIDENT_ID}-ATT-1"]

        added_again = client.post(
            f"/api/incidents/{INCIDENT_ID}/forms/1/attachments",
            json={"attachment_id": f"{INCIDENT_ID}-ATT-1"},
        )
        assert added_again.status_code == 200
        assert added_again.json()["attachment_ids"] == [f"{INCIDENT_ID}-ATT-1"]

        removed = client.delete(
            f"/api/incidents/{INCIDENT_ID}/forms/1/attachments/{INCIDENT_ID}-ATT-1"
        )
        assert removed.status_code == 200, removed.text
        assert removed.json()["attachment_ids"] == []

    _clear(db)


def test_form_attachment_rejects_wrong_owner():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    _seed_form(db)
    _seed_attachment(db, attachment_id=f"{INCIDENT_ID}-ATT-2", owner_id="other-record", owner_type="task")

    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/forms/1/attachments",
            json={"attachment_id": f"{INCIDENT_ID}-ATT-2"},
        )
        assert res.status_code == 422
        assert "owned by this form" in res.text

    _clear(db)
