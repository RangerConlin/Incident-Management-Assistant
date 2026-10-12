"""Read-through personnel lookup should support immediate incident check-in.

This mirrors a desktop client connected through cloud_router to a remote
server: the lookup endpoint refreshes local personnel from central first, then
the check-in write uses the refreshed local `person_record` to create incident
rows on that same remote server.
"""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.api.routers import aircraft as aircraft_router
from sarapp_db.api.routers import checkin as checkin_router
from sarapp_db.api.routers import equipment as equipment_router
from sarapp_db.api.routers import personnel as personnel_router
from sarapp_db.api.routers import vehicles as vehicles_router
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db

INCIDENT_ID = "TEST_PERSONNEL_READTHROUGH_CHECKIN"
PERSON_ID = "TEST-READTHROUGH-405021"
PERSON_DOC_ID = "TEST-READTHROUGH-PERSON-405021"


def _reset() -> None:
    get_master_db()["personnel"].delete_many({"_id": PERSON_DOC_ID})
    get_master_db()["vehicles"].delete_many({"_id": {"$regex": "^TEST-READTHROUGH-"}})
    get_master_db()["equipment"].delete_many({"_id": {"$regex": "^TEST-READTHROUGH-"}})
    get_master_db()["aircraft"].delete_many({"_id": {"$regex": "^TEST-READTHROUGH-"}})
    incident_db = get_incident_db(INCIDENT_ID)
    incident_db["resource_status"].delete_many({"resource_id": PERSON_ID})
    incident_db["resource_status"].delete_many({"resource_id": {"$regex": "^TEST-READTHROUGH-"}})
    incident_db["incident_personnel"].delete_many({"person_id": PERSON_ID})


def test_readthrough_lookup_then_checkin_creates_incident_rows(monkeypatch) -> None:
    _reset()
    calls: list[str] = []

    def fake_refresh(collection: str) -> None:
        calls.append(collection)
        get_master_db()["personnel"].update_one(
            {"_id": PERSON_DOC_ID},
            {
                "$set": {
                    "person_id": PERSON_ID,
                    "name": "Cloud Catalog Person",
                    "phone": "555-0100",
                    "updated_at": "2026-10-10T12:00:00",
                }
            },
            upsert=True,
        )

    monkeypatch.setattr(personnel_router, "refresh_collection_before_read", fake_refresh)

    try:
        app = create_app()
        with TestClient(app) as client:
            lookup = client.get("/api/master/personnel", params={"search": PERSON_ID, "limit": 20})
            assert lookup.status_code == 200, lookup.text
            matches = lookup.json()
            assert len(matches) == 1
            assert matches[0]["person_id"] == PERSON_ID
            person_record = matches[0]["person_record"]
            assert isinstance(person_record, int)

            response = client.put(
                f"/api/incidents/{INCIDENT_ID}/checkin/{person_record}",
                json={"status": "Checked In", "arrival_time": "2026-10-10T13:00:00"},
            )
            assert response.status_code == 200, response.text

        resource_status = get_incident_db(INCIDENT_ID)["resource_status"].find_one(
            {"entity_type": "personnel", "record_id": person_record}
        )
        assert resource_status is not None
        assert resource_status["resource_id"] == PERSON_ID
        assert resource_status["resource_name"] == "Cloud Catalog Person"
        assert resource_status["status"] == "Checked In"

        incident_person = get_incident_db(INCIDENT_ID)["incident_personnel"].find_one(
            {"person_record": person_record}
        )
        assert incident_person is not None
        assert incident_person["person_id"] == PERSON_ID
        assert incident_person["name"] == "Cloud Catalog Person"
        assert calls == ["personnel"]
    finally:
        _reset()


def test_checkin_personnel_search_route_refreshes_before_lookup(monkeypatch) -> None:
    _reset()
    calls: list[str] = []

    def fake_refresh(collection: str) -> None:
        calls.append(collection)
        get_master_db()["personnel"].update_one(
            {"_id": PERSON_DOC_ID},
            {"$set": {"person_id": PERSON_ID, "name": "Check-In Search Person"}},
            upsert=True,
        )

    monkeypatch.setattr(checkin_router, "refresh_collection_before_read", fake_refresh)

    try:
        app = create_app()
        with TestClient(app) as client:
            response = client.get(
                f"/api/incidents/{INCIDENT_ID}/checkin/personnel/search",
                params={"q": PERSON_ID, "limit": 20},
            )
            assert response.status_code == 200, response.text

        rows = response.json()
        assert len(rows) == 1
        assert rows[0]["person_id"] == PERSON_ID
        assert isinstance(rows[0]["person_record"], int)
        assert calls == [MasterCollections.PERSONNEL]
    finally:
        _reset()


def test_asset_readthrough_lookup_then_incident_resource_status(monkeypatch) -> None:
    _reset()
    calls: list[str] = []

    def fake_vehicle_refresh(collection: str) -> None:
        calls.append(collection)
        get_master_db()["vehicles"].update_one(
            {"_id": "TEST-READTHROUGH-VEHICLE"},
            {
                "$set": {
                    "vehicle_id": "TEST-READTHROUGH-VEHICLE-ID",
                    "make": "Ford",
                    "model": "F-150",
                }
            },
            upsert=True,
        )

    def fake_equipment_refresh(collection: str) -> None:
        calls.append(collection)
        get_master_db()["equipment"].update_one(
            {"_id": "TEST-READTHROUGH-EQUIPMENT"},
            {
                "$set": {
                    "equipment_id": "TEST-READTHROUGH-EQUIPMENT-ID",
                    "name": "Cloud Radio Cache",
                    "type": "Radio",
                }
            },
            upsert=True,
        )

    def fake_aircraft_refresh(collection: str) -> None:
        calls.append(collection)
        get_master_db()["aircraft"].update_one(
            {"_id": "TEST-READTHROUGH-AIRCRAFT"},
            {
                "$set": {
                    "aircraft_id": "TEST-READTHROUGH-AIRCRAFT-ID",
                    "callsign": "Cloud Helo",
                    "type": "Helicopter",
                }
            },
            upsert=True,
        )

    monkeypatch.setattr(vehicles_router, "refresh_collection_before_read", fake_vehicle_refresh)
    monkeypatch.setattr(equipment_router, "refresh_collection_before_read", fake_equipment_refresh)
    monkeypatch.setattr(aircraft_router, "refresh_collection_before_read", fake_aircraft_refresh)

    try:
        app = create_app()
        with TestClient(app) as client:
            vehicle_lookup = client.get(
                "/api/master/vehicles",
                params={"search": "TEST-READTHROUGH-VEHICLE-ID"},
            )
            equipment_lookup = client.get(
                "/api/master/equipment",
                params={"search": "TEST-READTHROUGH-EQUIPMENT-ID"},
            )
            aircraft_lookup = client.get(
                "/api/master/aircraft",
                params={"search": "TEST-READTHROUGH-AIRCRAFT-ID"},
            )

            assert vehicle_lookup.status_code == 200, vehicle_lookup.text
            assert equipment_lookup.status_code == 200, equipment_lookup.text
            assert aircraft_lookup.status_code == 200, aircraft_lookup.text

            vehicle = vehicle_lookup.json()[0]
            equipment = equipment_lookup.json()[0]
            aircraft = aircraft_lookup.json()[0]
            assert isinstance(vehicle["vehicle_record"], int)
            assert isinstance(equipment["equipment_record"], int)
            assert isinstance(aircraft["aircraft_record"], int)

            for entity_type, row, record_key, visible_key, name in (
                ("vehicle", vehicle, "vehicle_record", "vehicle_id", "Ford F-150"),
                ("equipment", equipment, "equipment_record", "equipment_id", "Cloud Radio Cache"),
                ("aircraft", aircraft, "aircraft_record", "aircraft_id", "Cloud Helo"),
            ):
                response = client.post(
                    f"/api/incidents/{INCIDENT_ID}/resource-status",
                    json={
                        "entity_type": entity_type,
                        "record_id": row[record_key],
                        "resource_id": row[visible_key],
                        "resource_name": name,
                        "resource_type": entity_type.title(),
                        "status": "Available",
                        "changed_by": "Check-In",
                    },
                )
                assert response.status_code == 201, response.text

                saved = get_incident_db(INCIDENT_ID)["resource_status"].find_one(
                    {"entity_type": entity_type, "record_id": row[record_key]}
                )
                assert saved is not None
                assert saved["resource_id"] == row[visible_key]
                assert saved["status"] == "Available"

        assert calls == [
            MasterCollections.VEHICLES,
            MasterCollections.EQUIPMENT,
            MasterCollections.AIRCRAFT,
        ]
    finally:
        _reset()
