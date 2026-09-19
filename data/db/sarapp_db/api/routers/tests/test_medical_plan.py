"""ICS-206 merged medical plan storage."""

from __future__ import annotations

import os
import pathlib
import sys

import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from bridge.medical_bridge import MedicalBridge
from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_incident_db
from utils import incident_context
from utils.state import AppState


INCIDENT_ID = "TEST_MEDICAL_PLAN"
OLD_COLLECTIONS = (
    "ics_206_ambulance_services",
    "ics_206_hospitals",
    "ics_206_air_ambulance",
    "ics_206_medical_comms",
    "ics_206_procedures",
    "ics_206_signatures",
)


def _clear(db):
    db["medical_plan"].delete_many({})
    db["ics_206_aid_stations"].delete_many({})
    for name in OLD_COLLECTIONS:
        db[name].delete_many({})


MED_LEAD = {"personnel_id": "7", "name": "Med Lead", "position": "MEDL"}
SAFETY = {"personnel_id": "9", "name": "Safety Officer", "position": "SOFR"}


def _bridge(person=MED_LEAD):
    bridge = MedicalBridge()
    bridge.current_person = lambda: dict(person)  # avoid the personnel API
    bridge.ensure_ics206_tables()
    return bridge


def test_ics206_sections_are_stored_in_medical_plan():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    incident_context.set_active_incident(INCIDENT_ID)
    AppState._active_incident_number = INCIDENT_ID
    AppState.set_active_op_period(1)

    bridge = _bridge()
    ambulance_id = bridge.add_record(
        "ambulance_services",
        {
            "name": "County EMS",
            "type": "Ground ALS",
            "service_level": 2,
            "phone": "555-0101",
            "location": "Station 1",
            "notes": "Primary transport",
        },
    )
    bridge.add_record(
        "hospitals",
        {
            "name": "General Hospital",
            "address": "1 Main St",
            "phone": "555-0202",
            "helipad": 1,
            "burn_center": 0,
            "level": "II",
        },
    )
    bridge.save_procedures("Call medical unit before transport.")

    plan_doc = db["medical_plan"].find_one({"incident_id": INCIDENT_ID, "op_period": 1})
    assert plan_doc is not None
    assert plan_doc["plan_id"] == f"{INCIDENT_ID}-MEDICAL-PLAN-1-V1"
    assert plan_doc["ambulance_services"][0]["id"] == ambulance_id
    assert plan_doc["ambulance_services"][0]["name"] == "County EMS"
    assert plan_doc["hospitals"][0]["name"] == "General Hospital"
    assert plan_doc["procedures"]["content"] == "Call medical unit before transport."
    assert plan_doc["version"] == 1
    assert plan_doc["approval_status"] == "not_started"
    assert plan_doc["signatures"]["prepared_by"] == "Med Lead"
    assert plan_doc["signatures"]["position"] == "MEDL"
    assert plan_doc["signatures"]["approved_by"] == ""
    for name in OLD_COLLECTIONS:
        assert db[name].count_documents({}) == 0

    app = create_app()
    with TestClient(app) as client:
        ambulances = client.get(f"/api/incidents/{INCIDENT_ID}/medical/ics206/ambulance-services", params={"op": 1})
        procedures = client.get(f"/api/incidents/{INCIDENT_ID}/medical/ics206/procedures", params={"op": 1})
    assert ambulances.status_code == 200
    assert ambulances.json()[0]["name"] == "County EMS"
    assert procedures.status_code == 200
    assert procedures.json()["content"] == "Call medical unit before transport."

    _clear(db)


def _approve_through_workflow(bridge, monkeypatch, app):
    """Run the real ICS-206 approval chain (MEDL, then SOFR) for the selected version."""
    from modules.approvals.service import ApprovalService
    from utils.api_client import api_client

    api_client.configure_test_transport(app)
    people = {"Medical Unit Leader": (7, MED_LEAD), "Safety Officer": (9, SAFETY)}
    monkeypatch.setattr(
        ApprovalService, "_resolve_actor", lambda self, role: (people[role][0], role)
    )
    incident_id, plan_id = bridge.approval_target()
    service = ApprovalService(incident_id)
    instance = service.start("ics_206", plan_id)
    bridge.mark_pending()
    assert [step.status for step in instance.steps] == ["active", "waiting"]
    for step_id, person_record, who in (("medl_approval", 7, MED_LEAD), ("sofr_approval", 9, SAFETY)):
        instance = service.get("ics_206", plan_id)
        assert service.can_sign(instance, step_id, person_record, "primary")
        assert not service.can_sign(instance, step_id, 123, "primary")
        bridge.current_person = lambda who=who: dict(who)
        instance = service.sign(
            instance,
            step_id=step_id,
            actor_id=str(person_record),
            role_at_time=who["position"],
            assignment_type="primary",
            action="approved",
        )
    assert instance.status == "approved"
    return instance


def test_ics206_versions_approval_workflow_and_lock(monkeypatch):
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    incident_context.set_active_incident(INCIDENT_ID)
    AppState._active_incident_number = INCIDENT_ID
    AppState.set_active_op_period(1)
    app = create_app()

    bridge = _bridge()
    bridge.add_record("hospitals", {"name": "General Hospital"})
    bridge.add_record("aid_stations", {"name": "Aid 1"})
    assert bridge.current_version() == 1
    assert bridge.approval_status() == "not_started"

    _approve_through_workflow(bridge, monkeypatch, app)
    # The approvals router wrote the outcome to this version's plan doc.
    assert db["medical_plan"].find_one({"version": 1})["approval_status"] == "approved"
    bridge.apply_approval_outcome("approved")
    signatures = bridge.get_signatures()
    assert signatures["prepared_by"] == "Med Lead"
    assert signatures["approved_by"] == "Safety Officer"
    assert signatures["approved_by_position"] == "SOFR"
    assert signatures["approved_at"]
    assert bridge.is_locked()
    with pytest.raises(RuntimeError, match="locked"):
        bridge.add_record("hospitals", {"name": "Nope"})
    with pytest.raises(RuntimeError, match="locked"):
        bridge.save_procedures("nope")

    # A version in review is locked too.
    bridge.current_person = lambda: dict(SAFETY)
    assert bridge.create_new_version("Added hospital") == 2
    assert not bridge.is_locked()
    bridge.mark_pending()
    with pytest.raises(RuntimeError, match="in review"):
        bridge.add_record("hospitals", {"name": "Nope"})
    bridge.apply_approval_outcome("rejected")
    assert bridge.approval_status() == "rejected"
    assert bridge.is_locked()

    # v3 is a draft copy prepared by whoever creates it.
    assert bridge.create_new_version("Fixed after rejection") == 3
    assert not bridge.is_locked()
    assert [row["name"] for row in bridge.list_table("hospitals")] == ["General Hospital"]
    assert [row["name"] for row in bridge.list_table("aid_stations")] == ["Aid 1"]
    signatures = bridge.get_signatures()
    assert signatures["prepared_by"] == "Safety Officer"
    assert signatures["approved_by"] == ""
    bridge.add_record("hospitals", {"name": "Second Hospital"})

    versions = bridge.list_versions()
    assert [(v["version"], v["approval_status"]) for v in versions] == [
        (1, "approved"), (2, "rejected"), (3, "not_started"),
    ]
    assert versions[2]["change_note"] == "Fixed after rejection"

    # v1 is untouched by edits to v3.
    bridge.select_version(1)
    assert [row["name"] for row in bridge.list_table("hospitals")] == ["General Hospital"]

    hospitals_url = f"/api/incidents/{INCIDENT_ID}/medical/ics206/hospitals"
    with TestClient(app) as client:
        # Default serves the latest *approved* version, not the newer drafts.
        default = client.get(hospitals_url, params={"op": 1})
        draft = client.get(hospitals_url, params={"op": 1, "version": 3})
        aid = client.get(f"/api/incidents/{INCIDENT_ID}/medical/ics206/aid-stations", params={"op": 1})
        assert [row["name"] for row in default.json()] == ["General Hospital"]
        assert [row["name"] for row in draft.json()] == ["General Hospital", "Second Hospital"]
        assert aid.status_code == 200, aid.text
        assert [row["name"] for row in aid.json()] == ["Aid 1"]

        # Once v3 is approved it becomes the default.
        bridge.select_version(3)
        _approve_through_workflow(bridge, monkeypatch, app)
        bridge.apply_approval_outcome("approved")
        default = client.get(hospitals_url, params={"op": 1})
        assert [row["name"] for row in default.json()] == ["General Hospital", "Second Hospital"]

    db["approval_instances"].delete_many({})
    db["approval_records"].delete_many({})
    _clear(db)


NEARBY_ROWS = [
    {
        "source_ref": "usgs_structures:amb-1",
        "name": "Jackson Community Ambulance",
        "address": "429 Ingham Street, Jackson, MI 49201",
        "lat": 42.2518,
        "lon": -84.4099,
        "distance_mi": 5.5,
        "source_date": "2018-08-01",
        "source": "test",
    },
    {
        "source_ref": "usgs_structures:amb-2",
        "name": "Huron Valley Ambulance",
        "address": "755 S Main Street, Chelsea, MI 48118",
        "lat": 42.3104,
        "lon": -84.0148,
        "distance_mi": 21.0,
        "source_date": "2016-08-12",
        "source": "test",
    },
]
HOSPITAL_ROWS = [
    {
        "source_ref": "cms:TEST-H1",
        "name": "Test General Hospital",
        "address": "205 N East Ave, Jackson, MI 49201",
        "phone": "(517) 555-0101",
        "lat": 42.2511,
        "lon": -84.3928,
        "distance_mi": 5.9,
        "source_date": "2026-09-19",
        "source": "test",
    },
    {
        "source_ref": "cms:TEST-H2",
        "name": "Test Community Hospital",
        "address": "168 S Howell St, Hillsdale, MI 49242",
        "phone": "",
        "lat": 41.9187,
        "lon": -84.6317,
        "distance_mi": 22.0,
        "source_date": "2026-09-19",
        "source": "test",
    },
]


def _nearby_setup(monkeypatch):
    """Incident with coordinates, patched external lookups, API routed in-process."""
    from sarapp_db.api.routers import medical as medical_router
    from sarapp_db.services.hospital_directory import HospitalDirectory
    from utils.api_client import api_client

    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    db["incident_profile"].delete_many({})
    db["incident_profile"].insert_one({"incident_id": INCIDENT_ID, "latitude": 42.18, "longitude": -84.46})
    incident_context.set_active_incident(INCIDENT_ID)
    AppState._active_incident_number = INCIDENT_ID
    AppState.set_active_op_period(1)

    calls = []

    def fake_ambulances(kind, lat, lon, radius_mi):
        calls.append(("ambulance", kind, lat, lon, radius_mi))
        return [dict(row) for row in NEARBY_ROWS]

    def fake_hospitals(self, lat, lon, radius_mi, refresh=False, states=None):
        calls.append(("hospital", lat, lon, radius_mi, refresh))
        return [dict(row) for row in HOSPITAL_ROWS], ["1 emergency hospital(s) could not be located: X (Y, MI)."]

    monkeypatch.setattr(medical_router, "find_nearby", fake_ambulances)
    monkeypatch.setattr(HospitalDirectory, "find_nearby", fake_hospitals)
    app = create_app()
    api_client.configure_test_transport(app)
    return db, app, medical_router, calls


def test_ics206_nearby_lookup_and_add(monkeypatch):
    from sarapp_db.services.nearby_medical import NearbyLookupError

    db, app, medical_router, calls = _nearby_setup(monkeypatch)
    try:
        bridge = _bridge()
        found = bridge.find_nearby("ambulance_services", 30)
        assert calls == [("ambulance", "ambulance-services", 42.18, -84.46, 30.0)]
        assert "ALS/BLS" in found["note"]
        rows = found["results"]
        assert [row["already_added"] for row in rows] == [False, False]

        assert bridge.add_nearby("ambulance_services", rows) == 2
        saved = bridge.list_table("ambulance_services")
        assert [row["name"] for row in saved] == ["Jackson Community Ambulance", "Huron Valley Ambulance"]
        assert saved[0]["location"] == "429 Ingham Street, Jackson, MI 49201"
        assert saved[0]["source_ref"] == "usgs_structures:amb-1"
        assert not saved[0]["type"] and not saved[0]["phone"]  # not in the source; preparer fills in

        # Already-listed facilities are flagged and never added twice.
        again = bridge.find_nearby("ambulance_services", 30)["results"]
        assert [row["already_added"] for row in again] == [True, True]
        assert bridge.add_nearby("ambulance_services", again) == 0
        assert len(bridge.list_table("ambulance_services")) == 2

        # Hospitals come from the directory: phone, coordinates and travel times carry over,
        # and directory warnings reach the caller.
        hospitals = bridge.find_nearby("hospitals", 40, refresh=True)
        assert calls[-1] == ("hospital", 42.18, -84.46, 40.0, True)
        assert "could not be located" in hospitals["warnings"][0]
        assert bridge.add_nearby("hospitals", hospitals["results"][:1]) == 1
        hospital = bridge.list_table("hospitals")[0]
        assert hospital["name"] == "Test General Hospital"
        assert hospital["phone"] == "(517) 555-0101"
        assert hospital["source_ref"] == "cms:TEST-H1"
        assert hospital["lat"] == 42.2511
        assert hospital["travel_time_ground_min"]

        # Locked versions reject additions.
        bridge.mark_pending()
        with pytest.raises(RuntimeError, match="locked"):
            bridge.add_nearby("ambulance_services", [dict(NEARBY_ROWS[0], source_ref="x", name="Other", already_added=False)])

        with TestClient(app) as client:
            assert client.get("/api/medical/nearby/fire-stations", params={"lat": 1, "lon": 1}).status_code == 404
            assert client.get("/api/medical/nearby/hospitals", params={"lat": 999, "lon": 1}).status_code == 422

            def failing(kind, lat, lon, radius_mi):
                raise NearbyLookupError("upstream down")

            monkeypatch.setattr(medical_router, "find_nearby", failing)
            down = client.get("/api/medical/nearby/ambulance-services", params={"lat": 1, "lon": 1})
            assert down.status_code == 502 and "upstream down" in down.json()["detail"]
    finally:
        db["incident_profile"].delete_many({})
        _clear(db)


def test_ics206_hidden_facilities_are_excluded_from_nearby(monkeypatch):
    from sarapp_db.mongo.database_manager import get_master_db

    db, app, medical_router, calls = _nearby_setup(monkeypatch)
    master = get_master_db()["nearby_facility_exclusions"]
    test_refs = [row["source_ref"] for row in NEARBY_ROWS + HOSPITAL_ROWS]
    master.delete_many({"source_ref": {"$in": test_refs}})
    try:
        bridge = _bridge()
        assert len(bridge.find_nearby("ambulance_services", 25)["results"]) == 2

        bridge.hide_nearby("ambulance_services", NEARBY_ROWS[0], "Closed or no longer exists")
        assert [r["name"] for r in bridge.find_nearby("ambulance_services", 25)["results"]] == ["Huron Valley Ambulance"]
        hidden = [row for row in bridge.list_hidden_nearby() if row["source_ref"] in test_refs]
        assert len(hidden) == 1
        assert hidden[0]["reason"] == "Closed or no longer exists"
        assert hidden[0]["excluded_by"] == "Med Lead"

        # Hiding is per facility kind (hospitals are unaffected) and cannot be done twice.
        assert len(bridge.find_nearby("hospitals", 25)["results"]) == 2
        bridge.hide_nearby("hospitals", HOSPITAL_ROWS[1], "Prison or correctional facility")
        assert [r["name"] for r in bridge.find_nearby("hospitals", 25)["results"]] == ["Test General Hospital"]
        with pytest.raises(Exception, match="already hidden"):
            bridge.hide_nearby("ambulance_services", NEARBY_ROWS[0], "again")

        for row in hidden + [r for r in bridge.list_hidden_nearby() if r["source_ref"] in test_refs and r["source_ref"] != hidden[0]["source_ref"]]:
            bridge.restore_nearby(row["id"])
        assert len(bridge.find_nearby("ambulance_services", 25)["results"]) == 2
        assert len(bridge.find_nearby("hospitals", 25)["results"]) == 2
    finally:
        master.delete_many({"source_ref": {"$in": test_refs}})
        db["incident_profile"].delete_many({})
        _clear(db)


def _cms(facility_id, name, street, city="SPRINGFIELD", phone="(555) 010-0000"):
    return {
        "facility_id": facility_id,
        "facility_name": name,
        "address": street,
        "citytown": city,
        "state": "ZZ",
        "zip_code": "11111",
        "countyparish": "TEST",
        "telephone_number": phone,
        "hospital_type": "Acute Care Hospitals",
        "hospital_ownership": "Voluntary non-profit - Private",
        "emergency_services": "Yes",
    }


def test_hospital_directory_refresh_cache_and_search(monkeypatch):
    from sarapp_db.mongo.database_manager import get_master_db
    from sarapp_db.services import hospital_directory as hd
    from sarapp_db.services.geocoding import GeocodeResult
    from sarapp_db.services.nearby_medical import NearbyLookupError

    coll = get_master_db()["hospital_directory"]
    coll.delete_many({"state": "ZZ"})
    directory = hd.HospitalDirectory(get_master_db())
    try:
        cms = [
            _cms("900001", "MERCY GENERAL HOSPITAL", "1 MAIN STREET"),
            _cms("900002", "ST LUKE'S MEDICAL CENTER OF THE VALLEY", "ONE TEST WAY", phone="(555) 010-0002"),
            _cms("900003", "NOWHERE HOSPITAL", "99999 UNKNOWN ROAD"),
        ]
        calls = {"cms": 0, "batch": []}

        def fake_cms(state):
            calls["cms"] += 1
            return [dict(row) for row in cms]

        def fake_batch(addresses):
            calls["batch"].append(dict(addresses))
            return {"900001": (42.20, -84.40)}  # 900002 and 900003 fall through to single lookups

        def fake_single(address):
            if address.startswith("1 TEST WAY"):
                return GeocodeResult(address=address, latitude=42.30, longitude=-84.50)
            return None

        monkeypatch.setattr(hd, "fetch_cms_er_hospitals", fake_cms)
        monkeypatch.setattr(hd, "batch_geocode", fake_batch)
        monkeypatch.setattr(hd, "geocode_address", fake_single)
        monkeypatch.setattr(hd, "zip_centroids", lambda zips: {})

        rows, warnings = directory.find_nearby(42.18, -84.46, 25, states=["ZZ"])
        assert [r["name"] for r in rows] == ["Mercy General Hospital", "St Luke's Medical Center of the Valley"]
        assert rows[0]["source_ref"] == "cms:900001"
        assert rows[0]["address"] == "1 Main Street, Springfield, ZZ 11111"
        assert rows[0]["phone"] == "(555) 010-0000"
        assert rows[0]["distance_mi"] < rows[1]["distance_mi"]
        assert len(warnings) == 1 and "Nowhere Hospital" in warnings[0]
        # Street numbers CMS spelled out are normalised before geocoding.
        assert calls["batch"][0]["900002"][0] == "1 TEST WAY"

        # Radius is honoured.
        near, _ = directory.find_nearby(42.18, -84.46, 5, states=["ZZ"])
        assert [r["name"] for r in near] == ["Mercy General Hospital"]

        # A fresh cache is used without contacting CMS again.
        assert calls["cms"] == 1

        # Hospitals no geocoder can place fall back to the ZIP area's centre, flagged approximate.
        monkeypatch.setattr(hd, "zip_centroids", lambda zips: {"11111": (42.19, -84.45)})
        rows, warnings = directory.find_nearby(42.18, -84.46, 25, refresh=True, states=["ZZ"])
        assert calls["cms"] == 2
        assert warnings == []
        by_name = {r["name"]: r for r in rows}
        assert by_name["Nowhere Hospital"]["location_approximate"] is True
        assert by_name["Mercy General Hospital"]["location_approximate"] is False

        # A forced refresh retires hospitals CMS no longer lists (closed / lost its ER).
        cms.pop(1)
        rows, _ = directory.find_nearby(42.18, -84.46, 25, refresh=True, states=["ZZ"])
        assert [r["name"] for r in rows] == ["Nowhere Hospital", "Mercy General Hospital"]
        assert calls["cms"] == 3
        assert coll.find_one({"cms_id": "900002"})["active"] is False

        # If CMS is unreachable the saved copy is still served, with a warning.
        def down(state):
            raise NearbyLookupError("CMS down")

        monkeypatch.setattr(hd, "fetch_cms_er_hospitals", down)
        rows, warnings = directory.find_nearby(42.18, -84.46, 25, refresh=True, states=["ZZ"])
        assert [r["name"] for r in rows] == ["Nowhere Hospital", "Mercy General Hospital"]
        assert any("Could not refresh ZZ" in w for w in warnings)

        # ...but an uncached state has nothing to fall back on.
        with pytest.raises(NearbyLookupError):
            directory.find_nearby(42.18, -84.46, 25, states=["ZY"])
    finally:
        coll.delete_many({"state": {"$in": ["ZZ", "ZY"]}})
