"""Communications log metadata must stay on the log entry document."""

from __future__ import annotations

import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_incident_db


INCIDENT_ID = "TEST_COMMS_METADATA"


def _clear(db):
    db["communications_log"].delete_many({})
    db["comms_log_audit"].delete_many({})


def test_comms_log_uses_entry_metadata_instead_of_audit_collection():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)

    app = create_app()
    with TestClient(app) as client:
        created = client.post(
            f"/api/incidents/{INCIDENT_ID}/comms-log",
            json={
                "message": "Initial traffic",
                "operator_user_id": "dispatcher-1",
                "operator_display_name": "Dispatcher One",
            },
        )
        assert created.status_code == 201
        entry_id = created.json()["id"]

        updated = client.patch(
            f"/api/incidents/{INCIDENT_ID}/comms-log/{entry_id}",
            json={"message": "Updated traffic", "operator_user_id": "dispatcher-2"},
        )
        assert updated.status_code == 200

        audit = client.get(f"/api/incidents/{INCIDENT_ID}/comms-log/{entry_id}/audit")
        assert audit.status_code == 200

    log_doc = db["communications_log"].find_one({"comms_id": f"{INCIDENT_ID}-COMMS-{entry_id}"})
    assert log_doc is not None
    assert log_doc["created_by"] == "dispatcher-1"
    assert log_doc["updated_by"] == "dispatcher-2"
    assert "audit" not in log_doc
    assert db["comms_log_audit"].count_documents({}) == 0

    actions = [entry["action"] for entry in audit.json()]
    assert actions == ["update", "create"]

    _clear(db)
