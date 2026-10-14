"""Master EMS agency catalogue: CRUD, duplicate detection, merge, audit log."""

from __future__ import annotations

import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db

BASE = "/api/master/ems-agencies"


def _clear(db):
    db[MasterCollections.EMS_AGENCIES].delete_many({})
    db[MasterCollections.EMS_AGENCY_AUDIT_LOG].delete_many({})


def test_ems_agency_crud_and_search():
    db = get_master_db()
    _clear(db)
    app = create_app()
    try:
        with TestClient(app) as client:
            created = client.post(BASE, json={
                "name": "County EMS",
                "type": "Ground Ambulance",
                "phone": "555-0101",
                "city": "Springfield",
            })
            assert created.status_code == 201, created.text
            agency = created.json()
            assert agency["id"] == 1
            assert agency["is_active"] is True
            assert agency["deleted"] is False

            missing_name = client.post(BASE, json={"type": "Ground Ambulance"})
            assert missing_name.status_code == 422

            bad_type = client.post(BASE, json={"name": "No Type"})
            assert bad_type.status_code == 422

            second = client.post(BASE, json={"name": "Air Rescue", "type": "Air Ambulance"})
            assert second.status_code == 201
            second_id = second.json()["id"]

            listed = client.get(BASE)
            assert [row["name"] for row in listed.json()] == ["Air Rescue", "County EMS"]

            searched = client.get(BASE, params={"search": "county"})
            assert [row["name"] for row in searched.json()] == ["County EMS"]

            by_ids = client.get(BASE, params={"ids": f"{agency['id']},{second_id}"})
            assert {row["name"] for row in by_ids.json()} == {"County EMS", "Air Rescue"}

            fetched = client.get(f"{BASE}/{agency['id']}")
            assert fetched.status_code == 200
            assert fetched.json()["phone"] == "555-0101"

            assert client.get(f"{BASE}/9999").status_code == 404

            updated = client.patch(
                f"{BASE}/{agency['id']}",
                json={"phone": "555-9999", "name": "County EMS", "type": "Ground Ambulance"},
            )
            assert updated.status_code == 200
            assert updated.json()["phone"] == "555-9999"

            deactivated = client.post(f"{BASE}/{agency['id']}/active", json={"active": False})
            assert deactivated.status_code == 200
            assert deactivated.json()["is_active"] is False

            active_only = client.get(BASE, params={"include_inactive": False})
            assert [row["name"] for row in active_only.json()] == ["Air Rescue"]

            reactivated = client.post(f"{BASE}/{agency['id']}/active", json={"active": True})
            assert reactivated.json()["is_active"] is True

            audit = client.get(f"{BASE}/audit-log")
            actions = [row["action"] for row in audit.json()]
            assert actions.count("ems_agency.create") == 2
            assert "ems_agency.update" in actions
            assert "ems_agency.deactivate" in actions
            assert "ems_agency.restore" in actions

            filtered = client.get(f"{BASE}/audit-log", params={"action": "ems_agency.update"})
            assert len(filtered.json()) == 1
    finally:
        _clear(db)


def test_ems_agency_duplicates_and_merge():
    db = get_master_db()
    _clear(db)
    app = create_app()
    try:
        with TestClient(app) as client:
            a = client.post(BASE, json={"name": "River Valley EMS", "type": "Ground Ambulance", "phone": "555-1234"}).json()
            b = client.post(BASE, json={"name": "River Valley E.M.S.", "type": "Ground Ambulance", "phone": "555-1234"}).json()
            c = client.post(BASE, json={"name": "Unrelated Agency", "type": "Other", "phone": "555-9000"}).json()

            duplicates = client.get(f"{BASE}/duplicates")
            assert duplicates.status_code == 200
            groups = duplicates.json()
            assert len(groups) == 1
            group = groups[0]
            assert sorted(group["candidate_ids"]) == sorted([a["id"], b["id"]])
            assert {m["name"] for m in group["members"]} == {"River Valley EMS", "River Valley E.M.S."}

            merged = client.post(f"{BASE}/merge", json={"survivor_id": a["id"], "duplicate_ids": [b["id"]]})
            assert merged.status_code == 200
            assert merged.json() == {"survivor_id": a["id"], "merged": [b["id"]]}

            remaining_active = client.get(BASE, params={"include_inactive": False})
            names = {row["name"] for row in remaining_active.json()}
            assert names == {"River Valley EMS", "Unrelated Agency"}

            audit = client.get(f"{BASE}/audit-log", params={"action": "ems_agency.merge"})
            assert len(audit.json()) == 1
            assert audit.json()[0]["detail"]["survivor"] == a["id"]
    finally:
        _clear(db)
