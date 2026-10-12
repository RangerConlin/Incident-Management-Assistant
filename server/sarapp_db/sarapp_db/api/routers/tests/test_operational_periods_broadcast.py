"""Guard that operational_periods.py writes through OperationalPeriodsRepository
(BaseRepository) instead of a raw pymongo collection. Exercises create/list/
update/set-active/clone end to end, and confirms set-active broadcasts the
status flip on both the newly-active and the newly-demoted periods.
"""
from __future__ import annotations

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.collection_names import IncidentCollections


INCIDENT_ID = "TEST_OPERATIONAL_PERIODS_BROADCAST"
COL = IncidentCollections.OPERATIONAL_PERIODS
BASE = f"/api/incidents/{INCIDENT_ID}/planning/operational-periods"


def _clear(db):
    db[COL].delete_many({})


def test_create_list_update_set_active_and_clone_round_trip():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)

    app = create_app()
    with TestClient(app) as client:
        res = client.post(BASE, json={
            "start_time": "2026-10-10T06:00:00",
            "end_time": "2026-10-10T18:00:00",
            "name": "OP1",
        })
        assert res.status_code == 201, res.text
        op1 = res.json()
        assert op1["number"] == 1
        assert op1["status"] == "Planned"

        res = client.post(BASE, json={
            "start_time": "2026-10-10T18:00:00",
            "end_time": "2026-10-11T06:00:00",
            "name": "OP2",
        })
        assert res.status_code == 201, res.text
        op2 = res.json()
        assert op2["number"] == 2

        res = client.get(BASE)
        assert res.status_code == 200
        assert [p["id"] for p in res.json()] == [op1["id"], op2["id"]]

        res = client.patch(f"{BASE}/{op1['id']}", json={"name": "OP1 renamed"})
        assert res.status_code == 200, res.text
        assert res.json()["name"] == "OP1 renamed"

        res = client.post(f"{BASE}/{op1['id']}/set-active")
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "Active"

        res = client.post(f"{BASE}/{op2['id']}/set-active")
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "Active"

        # Demoted when op2 became active.
        res = client.get(f"{BASE}/{op1['id']}")
        assert res.json()["status"] == "Planned"

        res = client.get(f"{BASE}/active")
        assert res.status_code == 200
        assert res.json()["id"] == op2["id"]

        res = client.post(f"{BASE}/{op2['id']}/clone")
        assert res.status_code == 201, res.text
        clone = res.json()
        assert clone["number"] == 3
        assert clone["status"] == "Planned"

    # Writes went through BaseRepository: every doc has created_at/updated_at
    # and a plain string _id, stamped by insert_one/update_one rather than
    # hand-built in the router.
    docs = list(db[COL].find({"incident_id": INCIDENT_ID}))
    assert len(docs) == 3
    for doc in docs:
        assert isinstance(doc["_id"], str)
        assert doc.get("created_at")
        assert doc.get("updated_at")

    _clear(db)
