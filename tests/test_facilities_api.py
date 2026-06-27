from __future__ import annotations

import pytest

from data.db.sarapp_db.api.app import create_app
from data.db.sarapp_db.api.routers import geocoding as geocoding_router
from data.db.sarapp_db.api.routers.geocoding import GeocodeRequest, ReverseGeocodeRequest
from data.db.sarapp_db.mongo.collection_names import IncidentCollections
from data.db.sarapp_db.mongo.database_manager import get_incident_db
from data.db.sarapp_db.services.geocoding import GeocodeResult
from modules.logistics.facilities.models import FacilityRecord
from modules.logistics.facilities.repository import ApiFacilitiesRepository
from utils.api_client import api_client


@pytest.fixture()
def app_client():
    incident_db = get_incident_db("INC-FAC-1")
    incident_db[IncidentCollections.FACILITIES].delete_many({})
    app = create_app()
    api_client.configure_test_transport(app)
    try:
        yield api_client
    finally:
        api_client.configure("http://localhost:8765")
        incident_db[IncidentCollections.FACILITIES].delete_many({})


def test_facilities_crud_and_primary_enforcement(app_client):
    repo = ApiFacilitiesRepository("INC-FAC-1")

    first = repo.save_facility(
        FacilityRecord(
            name="Main ICP",
            facility_type="command_post",
            address="123 Incident Rd",
            function_tags=["radio", "checkin"],
            is_primary=True,
        )
    )
    second = repo.save_facility(
        FacilityRecord(
            name="Backup ICP",
            facility_type="command_post",
            address="456 Fallback Ave",
            served_sections=["command", "logistics"],
            is_primary=True,
        )
    )

    rows = repo.list_facilities(facility_type="command_post")
    by_name = {row.name: row for row in rows}
    assert by_name["Main ICP"].is_primary is False
    assert by_name["Backup ICP"].is_primary is True

    loaded = repo.get_facility(first.id)
    assert loaded is not None
    assert loaded.name == "Main ICP"

    assert repo.delete_facility(second.id) is True
    remaining = repo.list_facilities(facility_type="command_post")
    assert [row.name for row in remaining] == ["Main ICP"]


def test_facility_manager_assignment_round_trips(app_client):
    repo = ApiFacilitiesRepository("INC-FAC-1")

    saved = repo.save_facility(
        FacilityRecord(
            name="North Staging",
            facility_type="staging",
            address="99 Supply Way",
            manager_personnel_id="241",
            manager_name="Taylor Brooks",
            contact_name="Taylor Brooks",
            contact_phone="555-0199",
        )
    )

    loaded = repo.get_facility(saved.id)
    assert loaded is not None
    assert loaded.manager_personnel_id == "241"
    assert loaded.manager_name == "Taylor Brooks"
    assert loaded.contact_name == "Taylor Brooks"


def test_geocoding_routes_use_shared_service(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        geocoding_router,
        "geocode_address",
        lambda address: GeocodeResult(f"Matched {address}", 44.1, -72.3),
    )
    monkeypatch.setattr(
        geocoding_router,
        "reverse_geocode_coordinates",
        lambda latitude, longitude: GeocodeResult("Reverse Match", latitude, longitude),
    )

    geocoded = geocoding_router.geocode(GeocodeRequest(address="1 Test Way"))
    reversed_row = geocoding_router.reverse_geocode(
        ReverseGeocodeRequest(latitude=44.1, longitude=-72.3)
    )

    assert geocoded["address"] == "Matched 1 Test Way"
    assert geocoded["latitude"] == 44.1
    assert reversed_row["address"] == "Reverse Match"


def test_incident_profile_can_store_icp_facility_reference(app_client):
    incident_number = "INC-ICP-FAC-001"
    existing = app_client.get("/api/incidents", params={"number": incident_number}) or []
    if existing:
        incident_id = existing[0]["id"]
    else:
        created = app_client.post(
            "/api/incidents",
            json={
                "number": incident_number,
                "name": "ICP Integration Test",
                "type": "Search",
                "icp_location": "Initial ICP",
            },
        )
        incident_id = created["id"]

    facility = app_client.post(
        f"/api/incidents/{incident_id}/facilities",
        json={
            "name": "Main Command Post",
            "facility_type": "command_post",
            "status": "active",
            "address": "101 Command Rd",
            "latitude": 35.5,
            "longitude": -80.25,
            "function_tags": ["radio"],
            "served_sections": ["command"],
            "is_primary": True,
        },
    )

    app_client.patch(
        f"/api/incidents/{incident_id}/profile",
        json={
            "icp_facility_id": facility["id"],
            "icp_location": "Main Command Post",
        },
    )

    profile = app_client.get(f"/api/incidents/{incident_id}/profile")
    assert profile["icp_facility_id"] == facility["id"]
    assert profile["icp_location"] == "Main Command Post"

    raw_doc = get_incident_db(incident_id)[IncidentCollections.INCIDENT_PROFILE].find_one({"incident_id": incident_id})
    assert raw_doc is not None
    assert raw_doc.get("latitude") == 35.5
    assert raw_doc.get("longitude") == -80.25
