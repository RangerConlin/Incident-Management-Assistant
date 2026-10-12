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


INCIDENT_ID = "TEST_SAFETY_CAP_ORM_HAZARDS"


def _clear() -> None:
    get_incident_db(INCIDENT_ID)[IncidentCollections.HAZARDS].delete_many({})


def test_cap_orm_hazard_endpoint_writes_canonical_hazards() -> None:
    _clear()
    app = create_app()

    with TestClient(app) as client:
        created = client.post(
            f"/api/incidents/{INCIDENT_ID}/safety/orm/hazards",
            json={
                "op_period": 1,
                "sub_activity": "Approach",
                "hazard_outcome": "Slip/fall",
                "initial_risk": "H",
                "control_text": "Use trekking poles",
                "residual_risk": "M",
                "implement_how": "Brief team",
                "implement_who": "Team lead",
            },
        )
        assert created.status_code == 201
        assert created.json()["implement_who"] == "Team lead"

        listed = client.get(f"/api/incidents/{INCIDENT_ID}/safety/orm/hazards", params={"op": 1})
        assert listed.status_code == 200
        assert [row["hazard_outcome"] for row in listed.json()] == ["Slip/fall"]

        form = client.get(f"/api/incidents/{INCIDENT_ID}/safety/orm/form", params={"op": 1})
        assert form.status_code == 200
        assert form.json()["highest_residual_risk"] == "M"

    docs = list(get_incident_db(INCIDENT_ID)[IncidentCollections.HAZARDS].find({"source": "cap_orm"}))
    assert len(docs) == 1
    assert docs[0]["title"] == "Approach"
    assert docs[0]["op_period_ids"] == [1]
    assert docs[0]["residual_risk"] == "M"

    _clear()
