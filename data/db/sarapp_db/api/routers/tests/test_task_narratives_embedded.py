import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_incident_db


INCIDENT_ID = "TESTCACHE_NARRATIVES"


def _reset_db():
    db = get_incident_db(INCIDENT_ID)
    db["tasks"].delete_many({})
    db["task_narratives"].delete_many({})
    db["tasks"].insert_one(
        {
            "_id": "task-1",
            "int_id": 7,
            "task_id": "T-007",
            "title": "Search north ridge",
            "narrative": [
                {
                    "entry_id": "existing-entry",
                    "task_id": 7,
                    "timestamp": "2026-07-11T10:00:00+00:00",
                    "narrative": "Initial assignment briefed.",
                    "entered_by": "1",
                    "team_num": "A",
                    "critical": 0,
                }
            ],
        }
    )
    return db


def test_task_narratives_crud_uses_embedded_task_array():
    db = _reset_db()
    app = create_app()
    with TestClient(app) as client:
        res = client.get(f"/api/incidents/{INCIDENT_ID}/narratives", params={"task_id": 7})
        assert res.status_code == 200
        assert [row["id"] for row in res.json()] == ["existing-entry"]

        legacy_update = client.patch(
            f"/api/incidents/{INCIDENT_ID}/narratives/existing-entry",
            json={"critical": 1},
        )
        assert legacy_update.status_code == 200
        assert legacy_update.json()["id"] == "existing-entry"
        assert legacy_update.json()["critical"] == 1

        created = client.post(
            f"/api/incidents/{INCIDENT_ID}/narratives",
            json={
                "task_id": 7,
                "timestamp": "2026-07-11T11:00:00+00:00",
                "narrative": "Located boot print.",
                "entered_by": "2",
                "team_num": "A",
                "critical": 1,
            },
        )
        assert created.status_code == 201
        created_id = created.json()["id"]

        task_doc = db["tasks"].find_one({"int_id": 7})
        entries = task_doc["narrative"]
        assert any(entry.get("id") == created_id and entry["narrative"] == "Located boot print." for entry in entries)
        assert db["task_narratives"].count_documents({}) == 0

        updated = client.patch(
            f"/api/incidents/{INCIDENT_ID}/narratives/{created_id}",
            json={"critical": 0, "team_num": "B"},
        )
        assert updated.status_code == 200
        assert updated.json()["critical"] == 0
        assert updated.json()["team_num"] == "B"

        deleted = client.delete(f"/api/incidents/{INCIDENT_ID}/narratives/{created_id}")
        assert deleted.status_code == 204
        task_doc = db["tasks"].find_one({"int_id": 7})
        assert all(entry.get("id") != created_id for entry in task_doc["narrative"])

    db["tasks"].delete_many({})
    db["task_narratives"].delete_many({})


def test_task_narratives_can_filter_embedded_entries():
    db = _reset_db()
    db["tasks"].update_one(
        {"int_id": 7},
        {
            "$push": {
                "narrative": {
                    "id": "critical-entry",
                    "task_id": 7,
                    "timestamp": "2026-07-11T12:00:00+00:00",
                    "narrative": "Critical clue found.",
                    "entered_by": "3",
                    "team_num": "B",
                    "critical": 1,
                }
            }
        },
    )

    app = create_app()
    with TestClient(app) as client:
        res = client.get(
            f"/api/incidents/{INCIDENT_ID}/narratives",
            params={"task_id": 7, "critical_only": True, "team": "B", "search": "clue"},
        )
        assert res.status_code == 200
        assert [row["id"] for row in res.json()] == ["critical-entry"]

    db["tasks"].delete_many({})
    db["task_narratives"].delete_many({})
