"""Guard the field-name contract between ic_overview's team/task readers and
the documents actually written by modules/operations (operations.py's
create_team/create_task/add_task_team). The teams collection uses int_id,
needs_attention, emergency_flag, and last_checkin_at - not team_id,
needs_assistance, or assigned_teams - and tasks embed assignments under
task_teams, not assigned_teams. These tests fail if the routers drift apart
again.
"""
from __future__ import annotations

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_incident_db


INCIDENT_ID = "TEST_IC_OVERVIEW"


def _realistic_team_doc(**overrides) -> dict:
    doc = {
        "int_id": 1,
        "name": "Team 1",
        "callsign": None,
        "team_leader": None,
        "leader_phone": None,
        "phone": None,
        "team_type": "GT",
        "status": "Available",
        "ci_status": "Available",
        "status_updated": None,
        "current_task_id": None,
        "location": None,
        "needs_attention": False,
        "emergency_flag": False,
        "last_checkin_at": None,
        "checkin_reference_at": None,
        "last_comm_ping": None,
    }
    doc.update(overrides)
    return doc


def _realistic_task_doc(**overrides) -> dict:
    doc = {
        "int_id": 1,
        "task_id": "T-001",
        "title": "Search Sector 4",
        "status": "Assigned",
        "due_time": None,
        "assignment": "",
        "task_teams": [],
    }
    doc.update(overrides)
    return doc


def _clear(db):
    db["teams"].delete_many({})
    db["tasks"].delete_many({})
    db["resource_requests"].delete_many({})
    db["logistics_resource_requests"].delete_many({})


def test_list_teams_reads_actual_operations_field_names():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    db["teams"].insert_one(_realistic_team_doc(
        int_id=7,
        name="Team 7",
        status="En Route",
        needs_attention=True,
        emergency_flag=True,
        last_checkin_at="2026-07-07T10:00:00-07:00",
    ))

    app = create_app()
    with TestClient(app) as client:
        res = client.get(f"/api/incidents/{INCIDENT_ID}/teams")
    assert res.status_code == 200
    teams = res.json()
    assert len(teams) == 1
    team = teams[0]
    assert team["team_id"] == 7
    assert team["team_name"] == "Team 7"
    assert team["status"] == "En Route"
    assert team["needs_assistance"] is True
    assert team["emergency"] is True
    assert team["last_checkin_ts"] is not None

    _clear(db)


def test_compute_alerts_fires_on_real_team_fields():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    overdue_ts = (datetime.now().astimezone() - timedelta(minutes=90)).isoformat(timespec="seconds")
    db["teams"].insert_one(_realistic_team_doc(
        int_id=1, name="Team 1", status="Enroute", needs_attention=False,
        emergency_flag=False, last_checkin_at=overdue_ts,
    ))
    db["teams"].insert_one(_realistic_team_doc(
        int_id=2, name="Team 2", status="Available", needs_attention=True,
        emergency_flag=False,
    ))
    db["teams"].insert_one(_realistic_team_doc(
        int_id=3, name="Team 3", status="Available", needs_attention=False,
        emergency_flag=True,
    ))

    app = create_app()
    with TestClient(app) as client:
        res = client.get(f"/api/incidents/{INCIDENT_ID}/alerts")
    assert res.status_code == 200
    alerts = res.json()
    types_by_team = {a["team_id"]: a["type"] for a in alerts}
    assert types_by_team.get(1) == "CHECKIN_OVERDUE"
    assert types_by_team.get(2) == "NEEDS_ASSISTANCE"
    assert types_by_team.get(3) == "EMERGENCY"

    _clear(db)


def test_task_summary_reads_task_teams_not_assigned_teams():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    due = (datetime.now().astimezone() + timedelta(hours=1)).isoformat(timespec="seconds")
    db["tasks"].insert_one(_realistic_task_doc(
        int_id=1, task_id="T-001", title="Search Sector 4", status="Assigned",
        due_time=due, assignment="",
        task_teams=[{"id": 1, "team_id": 7, "team_name": "Team 7"}],
    ))

    app = create_app()
    with TestClient(app) as client:
        res = client.get(f"/api/incidents/{INCIDENT_ID}/tasks/summary")
    assert res.status_code == 200
    body = res.json()
    assert body["counts"]["Planned"] == 1
    assert len(body["due"]) == 1
    assert body["due"][0]["assigned_to"] == "Team 7"

    _clear(db)


def test_logistics_counts_read_canonical_resource_requests():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)

    app = create_app()
    with TestClient(app) as client:
        created = client.post(
            f"/api/incidents/{INCIDENT_ID}/logistics/resource-requests",
            json={
                "title": "Need tarps",
                "priority": "HIGH",
                "status": "SUBMITTED",
                "created_by_id": "pytest",
                "items": [{"kind": "SUPPLY", "description": "Tarps", "quantity": 5}],
            },
        )
        assert created.status_code == 201

        counts = client.get(f"/api/incidents/{INCIDENT_ID}/logistics/counts")
        assert counts.status_code == 200

    body = counts.json()
    assert body["Submitted"] == 1
    assert db["resource_requests"].find_one({"title": "Need tarps"}) is not None
    assert db["logistics_resource_requests"].find_one({"title": "Need tarps"}) is None

    _clear(db)
