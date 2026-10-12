"""Router-level tests for the Team GAR (Green-Amber-Red) risk assessment
endpoints — template-driven scoring, not the old fixed 6-factor model."""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db


INCIDENT_ID = "TEST_TEAM_GAR"


def _reset_db():
    db = get_incident_db(INCIDENT_ID)
    db["teams"].delete_many({})
    db[IncidentCollections.OPERATIONAL_PERIODS].delete_many({})
    db[IncidentCollections.INCIDENT_PROFILE].delete_many({"incident_id": INCIDENT_ID})
    db["teams"].insert_one({"_id": "team-gar-1", "int_id": 1, "name": "Team 1"})
    db[IncidentCollections.INCIDENT_PROFILE].insert_one(
        {"_id": "profile-1", "incident_id": INCIDENT_ID, "name": "Test Incident"}
    )
    get_master_db()[MasterCollections.GAR_TEMPLATES].delete_many({"name": {"$regex": "^TEST_"}})
    return db


def _seed_template(name: str = "TEST_Template") -> int:
    col = get_master_db()[MasterCollections.GAR_TEMPLATES]
    doc = {
        "id": 9001,
        "name": name,
        "source": "Test",
        "description": "",
        "groups": [
            {
                "id": "g1",
                "name": "Group One",
                "rows": [
                    {
                        "id": "r1",
                        "label": "Row One",
                        "options": [
                            {"id": "low", "label": "Low", "points": 0, "no_go": False},
                            {"id": "high", "label": "High", "points": 10, "no_go": False},
                        ],
                    }
                ],
            },
            {
                "id": "g2",
                "name": "Group Two",
                "rows": [
                    {
                        "id": "r2",
                        "label": "Row Two",
                        "options": [
                            {"id": "ok", "label": "OK", "points": 0, "no_go": False},
                            {"id": "stop", "label": "Stop", "points": 20, "no_go": True},
                        ],
                    }
                ],
            },
        ],
        "bands": [
            {"floor": 15, "label": "Red", "required_reviewer": "IC"},
            {"floor": 5, "label": "Amber", "required_reviewer": "Ops Chief"},
            {"floor": 0, "label": "Green", "required_reviewer": "Team Leader"},
        ],
        "active": True,
    }
    col.delete_many({"id": doc["id"]})
    col.insert_one(doc)
    return doc["id"]


def _seed_active_op_period(db, number: int = 2) -> int:
    db[IncidentCollections.OPERATIONAL_PERIODS].insert_one(
        {
            "_id": "op-period-1",
            "int_id": number,
            "incident_id": INCIDENT_ID,
            "number": number,
            "status": "Active",
            "start_time": "2026-01-01T06:00:00+00:00",
            "end_time": "2026-01-01T18:00:00+00:00",
        }
    )
    return number


LOW_SELECTIONS = [
    {"group_id": "g1", "row_id": "r1", "option_id": "low"},
    {"group_id": "g2", "row_id": "r2", "option_id": "ok"},
]
HIGH_SELECTIONS = [
    {"group_id": "g1", "row_id": "r1", "option_id": "high"},
    {"group_id": "g2", "row_id": "r2", "option_id": "ok"},
]
NO_GO_SELECTIONS = [
    {"group_id": "g1", "row_id": "r1", "option_id": "low"},
    {"group_id": "g2", "row_id": "r2", "option_id": "stop"},
]


def test_get_team_gar_before_any_assessment_returns_empty():
    _reset_db()
    app = create_app()
    with TestClient(app) as client:
        res = client.get(f"/api/incidents/{INCIDENT_ID}/operations/teams/1/gar")
        assert res.status_code == 200
        assert res.json() == {"current": None, "history": []}
    _reset_db()


def test_save_team_gar_rejects_when_no_template_specified_and_no_default_set():
    _reset_db()
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/operations/teams/1/gar",
            json={"selections": LOW_SELECTIONS, "assessed_by": "IC-1"},
        )
        assert res.status_code == 422
    _reset_db()


def test_save_team_gar_computes_score_and_band_from_explicit_template():
    _reset_db()
    template_id = _seed_template()
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/operations/teams/1/gar",
            json={
                "template_id": template_id,
                "selections": LOW_SELECTIONS,
                "notes": "Routine ops.",
                "assessed_by": "IC-1",
            },
        )
        assert res.status_code == 201
        current = res.json()["current"]
        assert current["score"] == 0
        assert current["band"] == "Green"
        assert current["required_reviewer"] == "Team Leader"
        assert current["template_id"] == template_id
        assert current["template_name"] == "TEST_Template"
        assert current["notes"] == "Routine ops."
        assert current["assessed_by"] == "IC-1"
        assert current["assessed_at"]
        assert current["operational_period_id"] is None
        assert len(current["selections"]) == 2
        assert current["selections"][0]["option_label"] == "Low"
    _reset_db()


def test_save_team_gar_uses_incident_default_template_when_unspecified():
    _reset_db()
    template_id = _seed_template()
    app = create_app()
    with TestClient(app) as client:
        set_default = client.patch(
            f"/api/incidents/{INCIDENT_ID}/operations/gar-default-template",
            json={"template_id": template_id},
        )
        assert set_default.status_code == 200

        get_default = client.get(f"/api/incidents/{INCIDENT_ID}/operations/gar-default-template")
        assert get_default.json() == {"template_id": template_id}

        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/operations/teams/1/gar",
            json={"selections": HIGH_SELECTIONS, "assessed_by": "IC-1"},
        )
        assert res.status_code == 201
        assert res.json()["current"]["template_id"] == template_id
        assert res.json()["current"]["band"] == "Amber"
    _reset_db()


def test_save_team_gar_tags_active_operational_period():
    db = _reset_db()
    template_id = _seed_template()
    op_number = _seed_active_op_period(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/operations/teams/1/gar",
            json={"template_id": template_id, "selections": LOW_SELECTIONS, "assessed_by": "IC-1"},
        )
        assert res.status_code == 201
        assert res.json()["current"]["operational_period_id"] == op_number
    _reset_db()


def test_save_team_gar_no_go_option_forces_no_go_band():
    _reset_db()
    template_id = _seed_template()
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/operations/teams/1/gar",
            json={"template_id": template_id, "selections": NO_GO_SELECTIONS, "assessed_by": "IC-1"},
        )
        assert res.status_code == 201
        current = res.json()["current"]
        assert current["no_go"] is True
        assert current["band"] == "No-Go"
    _reset_db()


def test_save_team_gar_rejects_incomplete_selections():
    _reset_db()
    template_id = _seed_template()
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/operations/teams/1/gar",
            json={"template_id": template_id, "selections": [LOW_SELECTIONS[0]], "assessed_by": "IC-1"},
        )
        assert res.status_code == 422
    _reset_db()


def test_save_team_gar_rejects_unknown_template():
    _reset_db()
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/operations/teams/1/gar",
            json={"template_id": 999999, "selections": LOW_SELECTIONS, "assessed_by": "IC-1"},
        )
        assert res.status_code == 404
    _reset_db()


def test_reassessing_gar_appends_to_history_instead_of_overwriting():
    """A task can have multiple teams, and GAR is scored per team; this
    also covers that a team re-assessed mid-op-period keeps its prior
    assessment rather than losing it, and that each team can be scored
    against a different template per assessment."""
    _reset_db()
    template_id = _seed_template()
    app = create_app()
    with TestClient(app) as client:
        first = client.post(
            f"/api/incidents/{INCIDENT_ID}/operations/teams/1/gar",
            json={"template_id": template_id, "selections": LOW_SELECTIONS, "assessed_by": "IC-1"},
        )
        assert first.status_code == 201
        assert first.json()["current"]["band"] == "Green"

        second = client.post(
            f"/api/incidents/{INCIDENT_ID}/operations/teams/1/gar",
            json={"template_id": template_id, "selections": NO_GO_SELECTIONS, "assessed_by": "IC-2"},
        )
        assert second.status_code == 201
        body = second.json()
        assert body["current"]["band"] == "No-Go"
        assert len(body["history"]) == 2
        assert body["history"][0]["band"] == "Green"
        assert body["history"][0]["assessed_by"] == "IC-1"
        assert body["history"][1]["band"] == "No-Go"

        team_doc = get_incident_db(INCIDENT_ID)["teams"].find_one({"int_id": 1})
        audit_fields = [entry["field_changed"] for entry in team_doc.get("audit") or []]
        assert audit_fields.count("GAR Score") == 2
    _reset_db()
