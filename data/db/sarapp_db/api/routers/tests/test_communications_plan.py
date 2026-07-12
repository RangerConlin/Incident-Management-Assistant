"""Communications plan records are scoped per operational period."""

from __future__ import annotations

import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_incident_db


INCIDENT_ID = "TEST_COMMS_PLAN"


def _clear(db):
    db["communications_plan"].delete_many({})
    db["ics_205_instances"].delete_many({})


def test_communications_plan_is_saved_per_operational_period():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)

    app = create_app()
    with TestClient(app) as client:
        first = client.put(
            f"/api/incidents/{INCIDENT_ID}/communications-plan",
            json={
                "op_period_id": "1",
                "special_instructions": "Use command net for priority traffic.",
                "phone_numbers": [{"label": "COML", "number": "555-0101"}],
                "notes": "Primary plan.",
            },
        )
        assert first.status_code == 200

        second = client.put(
            f"/api/incidents/{INCIDENT_ID}/communications-plan",
            json={
                "op_period_id": "2",
                "special_instructions": "Switch to backup repeater after 1800.",
            },
        )
        assert second.status_code == 200

        fetched = client.get(
            f"/api/incidents/{INCIDENT_ID}/communications-plan",
            params={"op_period_id": "1"},
        )
        assert fetched.status_code == 200

    body = fetched.json()
    assert body["plan_id"] == f"{INCIDENT_ID}-COMMS-PLAN-1"
    assert body["op_period_id"] == "1"
    assert body["special_instructions"] == "Use command net for priority traffic."
    assert body["phone_numbers"] == [{"label": "COML", "number": "555-0101"}]
    assert db["communications_plan"].count_documents({"incident_id": INCIDENT_ID}) == 2
    assert db["ics_205_instances"].count_documents({}) == 0

    _clear(db)
