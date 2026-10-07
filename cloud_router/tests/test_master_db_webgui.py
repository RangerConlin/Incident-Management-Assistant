"""Coverage for the central master-catalog web GUI (`/gui/...`).

Uses an https base_url since the session cookie is marked Secure (matching
how this is actually served, through Traefik TLS) — over plain http,
httpx's cookie jar would drop it between requests in the same test client.
"""

import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import os

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from router.app import create_router_app


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("SARAPP_CLOUD_ROUTER_MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("CENTRAL_MASTER_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("CENTRAL_MASTER_ADMIN_PASSWORD", "test-secret")
    monkeypatch.setenv("CENTRAL_MASTER_SESSION_SECRET", "test-session-secret")
    # create_master_app() sets these two directly on os.environ (by design —
    # in cloud_router's own real process, that's a one-time, permanent
    # process-wide config step, same as any other server runtime setting
    # SARAPP_MONGO_URI once at startup). In a shared test process that would
    # otherwise leak into unrelated tests after this one, since monkeypatch
    # can only auto-revert keys it already owns — pre-seed them here so its
    # teardown restores the pre-test value regardless of create_master_app()
    # reassigning the same key again internally.
    monkeypatch.setenv("SARAPP_MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("SARAPP_MASTER_DB_NAME", "sarapp_central_master")
    app = create_router_app()
    return TestClient(app, base_url="https://testserver", follow_redirects=False)


def _login(client: TestClient) -> None:
    response = client.post(
        "/central-master/gui/login",
        data={"username": "admin", "password": "test-secret"},
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/central-master/gui"


def _clear_personnel():
    from sarapp_db.mongo.database_manager import get_client

    get_client()["sarapp_central_master"]["personnel"].delete_many({"name": {"$regex": "^GUI Test"}})


def _clear_equipment():
    from sarapp_db.mongo.database_manager import get_client

    get_client()["sarapp_central_master"]["equipment"].delete_many({"name": {"$regex": "^GUI Test"}})


def _clear_vehicles():
    from sarapp_db.mongo.database_manager import get_client

    get_client()["sarapp_central_master"]["vehicles"].delete_many({"vehicle_id": {"$regex": "^GUI Test"}})


def _clear_aircraft():
    from sarapp_db.mongo.database_manager import get_client

    get_client()["sarapp_central_master"]["aircraft"].delete_many({"aircraft_id": {"$regex": "^GUI Test"}})


def _clear_resource_types():
    from sarapp_db.mongo.collection_names import MasterCollections
    from sarapp_db.mongo.database_manager import get_client

    db = get_client()["sarapp_central_master"]
    db[MasterCollections.RESOURCE_TYPES].delete_many(
        {"name": {"$regex": "^GUI Test"}}
    )
    db[MasterCollections.RESOURCE_CAPABILITIES].delete_many(
        {"name": {"$regex": "^GUI Test"}}
    )


def _clear_organization_catalog():
    from sarapp_db.mongo.collection_names import MasterCollections
    from sarapp_db.mongo.database_manager import get_client

    db = get_client()["sarapp_central_master"]
    db[MasterCollections.ORGANIZATION_TYPES].delete_many({"name": {"$regex": "^GUI Test"}})
    db[MasterCollections.ORGANIZATIONS].delete_many({"name": {"$regex": "^GUI Test"}})
    db[MasterCollections.RANK_STRUCTURES].delete_many({"name": {"$regex": "^GUI Test"}})
    db[MasterCollections.RANKS].delete_many({"rank_name": {"$regex": "^GUI Test"}})


def _clear_console_users():
    from sarapp_db.mongo.database_manager import get_client

    get_client()["sarapp_central_master"]["master_gui_users"].delete_many({"username": {"$regex": "^gui-test"}})


def _clear_seed_catalog_rows():
    from sarapp_db.mongo.collection_names import MasterCollections
    from sarapp_db.mongo.database_manager import get_client

    org_type_names = [
        "Air Agency", "Ground SAR", "Law Enforcement", "Fire/Rescue", "EMS",
        "Government", "Volunteer Organization", "NGO", "Federal", "State",
        "County", "Municipal", "Military", "Private Contractor", "Amateur Radio",
        "Aviation Support", "Communications Unit", "Other",
    ]
    rank_structure_names = [
        "Fire Department (Standard)",
        "Law Enforcement (Standard)",
        "EMS (Standard)",
        "Search and Rescue (Standard)",
        "Volunteer / NGO (Standard)",
        "Civil Air Patrol (Standard)",
    ]
    rank_names = [
        "Firefighter", "Engineer / Driver", "Lieutenant", "Captain",
        "Battalion Chief", "Division Chief", "Assistant Chief", "Deputy Chief",
        "Fire Chief", "Police Officer", "Senior Police Officer", "Corporal",
        "Sergeant", "Major / Commander", "Chief of Police", "EMT",
        "Advanced EMT", "Paramedic", "Field Training Officer", "Supervisor",
        "Chief", "Member", "Senior Member", "Team Leader", "Operations Leader",
        "Planning Lead", "Logistics Lead", "Section Chief", "Incident Commander",
        "Volunteer", "Lead Volunteer", "Coordinator", "Manager", "Director",
        "Cadet Airman Basic", "Cadet Airman", "Cadet Airman First Class",
        "Cadet Senior Airman", "Cadet Staff Sergeant", "Cadet Technical Sergeant",
        "Cadet Master Sergeant", "Cadet Senior Master Sergeant",
        "Cadet Chief Master Sergeant", "Cadet Second Lieutenant",
        "Cadet First Lieutenant", "Cadet Captain", "Cadet Major",
        "Cadet Lieutenant Colonel", "Cadet Colonel", "Second Lieutenant",
        "First Lieutenant", "Major", "Lieutenant Colonel", "Colonel",
    ]
    db = get_client()["sarapp_central_master"]
    db[MasterCollections.ORGANIZATION_TYPES].delete_many({"name": {"$in": org_type_names}})
    db[MasterCollections.RANK_STRUCTURES].delete_many({"name": {"$in": rank_structure_names}})
    db[MasterCollections.RANKS].delete_many({"rank_name": {"$in": rank_names}})




def test_gui_requires_login(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/central-master/gui")

    assert response.status_code == 303
    assert response.headers["location"] == "/central-master/gui/login"


def test_login_with_wrong_password_redirects_back_to_login(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.post(
        "/central-master/gui/login",
        data={"username": "admin", "password": "wrong"},
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/central-master/gui/login"


def test_login_then_index_lists_collections(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)

    response = client.get("/central-master/gui")

    assert response.status_code == 200
    assert "Personnel" in response.text
    assert "Equipment" in response.text
    assert "Vehicles" in response.text
    assert "Organization Types" in response.text
    assert "Rank Structures" in response.text
    assert "Resource Types" in response.text
    assert "Resource Capabilities" in response.text
    assert "Organizations" in response.text
    assert 'href="/central-master/gui/ranks"' not in response.text
    assert "Console Users" in response.text


def test_create_and_edit_personnel_record(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_personnel()
    try:
        created = client.post(
            "/central-master/gui/personnel/new",
            data={"name": "GUI Test Person"},
        )
        assert created.status_code == 303
        assert created.headers["location"] == "/central-master/gui/personnel"

        listing = client.get("/central-master/gui/personnel")
        assert "GUI" in listing.text
        assert "Test Person" in listing.text

        from sarapp_db.api.routers.personnel import list_personnel

        doc = next(d for d in list_personnel(search="", limit=200) if d["name"] == "GUI Test Person")
        record_id = doc["person_record_master"]

        edit_page = client.get(f"/central-master/gui/personnel/{record_id}")
        assert edit_page.status_code == 200
        assert "GUI Test Person" in edit_page.text
        assert "Emergency Primary Name" in edit_page.text
        assert "Contact Address 1" in edit_page.text
        assert "Certifications" in edit_page.text

        updated = client.post(
            f"/central-master/gui/personnel/{record_id}",
            data={
                "name": "GUI Test Person Updated",
                "emergency_primary_name": "GUI Test Contact",
                "contact_city": "Testville",
            },
        )
        assert updated.status_code == 303

        edit_page_after = client.get(f"/central-master/gui/personnel/{record_id}")
        assert "GUI Test Person Updated" in edit_page_after.text
        assert "GUI Test Contact" in edit_page_after.text
        assert "Testville" in edit_page_after.text
    finally:
        _clear_personnel()


def test_personnel_organization_and_rank_are_catalog_dropdowns(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_personnel()
    _clear_organization_catalog()
    try:
        client.post(
            "/central-master/gui/rank-structures/new",
            data={"name": "GUI Test Personnel Rank Structure", "is_active": "on"},
        )

        from sarapp_db.api.routers.organizations import list_rank_structures

        structure = next(d for d in list_rank_structures(search="GUI Test Personnel Rank Structure"))
        structure_id = structure["int_id"]
        client.post(
            "/central-master/gui/ranks/new",
            data={
                "rank_structure_id": str(structure_id),
                "rank_code": "TL",
                "rank_name": "GUI Test Team Leader",
                "short_display": "TL",
                "sort_order": "1",
                "is_active": "on",
            },
        )
        client.post(
            "/central-master/gui/organizations/new",
            data={
                "name": "GUI Test Personnel Org",
                "default_rank_structure_id": str(structure_id),
                "is_active": "on",
            },
        )

        new_page = client.get("/central-master/gui/personnel/new")
        assert new_page.status_code == 200
        assert 'name="home_unit"' in new_page.text
        assert "GUI Test Personnel Org" in new_page.text
        assert 'data-combo-depends="home_unit"' in new_page.text
        assert 'data-combo-depmap-for="home_unit"' in new_page.text
        assert "TL - GUI Test Team Leader" in new_page.text
        assert 'name="emergency_blood_type"' in new_page.text
        assert "O+" in new_page.text
        assert 'name="contact_state"' in new_page.text
        assert "MI" in new_page.text
    finally:
        _clear_personnel()
        _clear_organization_catalog()


def test_personnel_grid_supports_inline_field_edit(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_personnel()
    try:
        client.post("/central-master/gui/personnel/new", data={"name": "GUI Test Inline Person"})

        from sarapp_db.api.routers.personnel import list_personnel

        doc = next(d for d in list_personnel(search="", limit=200) if d["name"] == "GUI Test Inline Person")
        record_id = doc["person_record_master"]

        listing = client.get("/central-master/gui/personnel")
        assert 'data-inline-collection="personnel"' in listing.text
        assert "Personnel ID" in listing.text
        assert 'data-field="person_id"' in listing.text
        assert 'class="inline-cell"' in listing.text
        assert 'data-editor="text"' in listing.text
        assert 'data-editor="checkbox"' in listing.text
        assert 'data-editor="select"' in listing.text
        assert 'data-rank-by-org=' in listing.text

        updated = client.post(
            f"/central-master/gui/personnel/{record_id}/inline/callsign", data={"value": "Echo-9"}
        )
        assert updated.status_code == 200
        assert updated.json()["display"] == "Echo-9"

        medic_updated = client.post(
            f"/central-master/gui/personnel/{record_id}/inline/is_medic", data={"value": "1"}
        )
        assert medic_updated.status_code == 200

        rejected = client.post(
            f"/central-master/gui/personnel/{record_id}/inline/notes", data={"value": "nope"}
        )
        assert rejected.status_code == 404

        refreshed = next(d for d in list_personnel(search="", limit=200) if d["person_record_master"] == record_id)
        assert refreshed["callsign"] == "Echo-9"
        assert refreshed["is_medic"] is True
    finally:
        _clear_personnel()


def test_asset_catalogs_use_searchable_organization_picker(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_equipment()
    _clear_vehicles()
    _clear_aircraft()
    _clear_resource_types()
    _clear_organization_catalog()
    try:
        from sarapp_db.mongo.collection_names import MasterCollections
        from sarapp_db.mongo.database_manager import get_client

        get_client()["sarapp_central_master"][MasterCollections.RESOURCE_TYPES].insert_one({
            "_id": "gui-test-vehicle-resource-type",
            "resource_type_id": "901",
            "name": "GUI Test Vehicle Resource Type",
            "resource_name": "GUI Test Vehicle Resource Type",
            "category": "Vehicle",
            "source": "AHJ Custom",
            "is_active": True,
        })
        client.post(
            "/central-master/gui/organizations/new",
            data={
                "name": "GUI Test Asset Org",
                "short_name": "GTAO",
                "is_active": "on",
            },
        )

        for route in (
            "/central-master/gui/equipment/new",
            "/central-master/gui/vehicles/new",
            "/central-master/gui/aircraft/new",
        ):
            page = client.get(route)
            assert page.status_code == 200
            assert 'name="organization"' in page.text
            assert 'data-fk-combo="1"' in page.text
            assert "GUI Test Asset Org" in page.text

        vehicle_page = client.get("/central-master/gui/vehicles/new")
        assert "Passenger Vehicle" in vehicle_page.text
        assert "In Service" in vehicle_page.text
        assert 'type="number" step="1" name="year"' in vehicle_page.text
        assert 'type="number" step="1" name="capacity"' in vehicle_page.text
        assert 'name="resource_type_id"' in vehicle_page.text
        assert "GUI Test Vehicle Resource Type (Vehicle - AHJ Custom)" in vehicle_page.text

        aircraft_page = client.get("/central-master/gui/aircraft/new")
        assert "Helicopter" in aircraft_page.text
        assert "Out of Service" in aircraft_page.text
        assert "Jet A" in aircraft_page.text
        assert "Advanced" in aircraft_page.text
        assert 'type="number" step="1" name="range_nm"' in aircraft_page.text
        assert 'type="number" step="0.1" name="endurance_hr"' in aircraft_page.text
        assert 'type="checkbox" name="radio_vhf_air"' in aircraft_page.text
        assert 'type="checkbox" name="cap_ifr"' in aircraft_page.text
        assert 'name="base"' in aircraft_page.text
        assert "<datalist" in aircraft_page.text

        client.post(
            "/central-master/gui/equipment/new",
            data={"name": "GUI Test Org Equipment", "organization": "GUI Test Asset Org"},
        )
        client.post(
            "/central-master/gui/vehicles/new",
            data={"vehicle_id": "GUI Test Org Vehicle", "organization": "GUI Test Asset Org"},
        )
        client.post(
            "/central-master/gui/aircraft/new",
            data={"aircraft_id": "GUI Test Org Aircraft", "organization": "GUI Test Asset Org"},
        )

        for route in (
            "/central-master/gui/equipment",
            "/central-master/gui/vehicles",
            "/central-master/gui/aircraft",
        ):
            listing = client.get(route)
            assert listing.status_code == 200
            assert 'data-inline-collection=' in listing.text
            assert 'data-field="organization"' in listing.text
            assert 'data-editor="select"' in listing.text
            assert "GTAO - GUI Test Asset Org" in listing.text

        vehicle_listing = client.get("/central-master/gui/vehicles")
        assert 'data-field="type_id"' in vehicle_listing.text
        assert 'data-field="status_id"' in vehicle_listing.text
        assert "Passenger Vehicle" in vehicle_listing.text
        assert "Available" in vehicle_listing.text
    finally:
        _clear_equipment()
        _clear_vehicles()
        _clear_aircraft()
        _clear_resource_types()
        _clear_organization_catalog()


def test_organization_rank_foreign_keys_use_searchable_pickers(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_organization_catalog()
    try:
        client.post(
            "/central-master/gui/organization-types/new",
            data={"name": "GUI Test Org Type", "is_active": "on"},
        )
        client.post(
            "/central-master/gui/rank-structures/new",
            data={"name": "GUI Test Rank Structure", "is_active": "on"},
        )

        rank_structure_page = client.get("/central-master/gui/rank-structures/new")
        assert rank_structure_page.status_code == 200
        assert 'name="organization_type_id"' in rank_structure_page.text
        assert 'data-fk-combo="1"' in rank_structure_page.text
        assert "GUI Test Org Type" in rank_structure_page.text

        organization_page = client.get("/central-master/gui/organizations/new")
        assert organization_page.status_code == 200
        assert 'name="parent_organization_id"' in organization_page.text
        assert 'name="organization_type_id"' in organization_page.text
        assert 'name="default_rank_structure_id"' in organization_page.text
        assert "GUI Test Rank Structure" in organization_page.text

        rank_page = client.get("/central-master/gui/ranks/new")
        assert rank_page.status_code == 200
        assert 'name="rank_structure_id"' in rank_page.text
        assert 'data-fk-combo="1"' in rank_page.text
        assert "GUI Test Rank Structure" in rank_page.text
    finally:
        _clear_organization_catalog()


def test_resource_type_catalogs_use_desktop_control_types(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_resource_types()
    try:
        type_page = client.get("/central-master/gui/resource-types/new")
        assert type_page.status_code == 200
        assert 'name="category"' in type_page.text
        assert "Vehicle" in type_page.text
        assert 'name="source"' in type_page.text
        assert "AHJ Custom" in type_page.text
        assert 'type="number" step="0.1" name="typical_quantity"' in type_page.text
        assert 'type="number" step="1" name="typical_team_size"' in type_page.text
        assert 'type="checkbox" name="is_kit_cache"' in type_page.text
        assert 'type="checkbox" name="is_consumable"' in type_page.text
        assert 'type="checkbox" name="is_active" checked' in type_page.text

        created_type = client.post(
            "/central-master/gui/resource-types/new",
            data={
                "name": "GUI Test Resource Type",
                "resource_name": "GUI Test Resource Type Display",
                "category": "Vehicle",
                "source": "AHJ Custom",
                "typical_quantity": "2.5",
                "typical_team_size": "4",
                "is_active": "on",
            },
        )
        assert created_type.status_code == 303

        capability_page = client.get("/central-master/gui/resource-capabilities/new")
        assert capability_page.status_code == 200
        assert 'type="checkbox" name="is_active" checked' in capability_page.text

        created_capability = client.post(
            "/central-master/gui/resource-capabilities/new",
            data={
                "name": "GUI Test Capability",
                "category": "Vehicle",
                "description": "Cloud GUI test",
                "is_active": "on",
            },
        )
        assert created_capability.status_code == 303

        type_listing = client.get("/central-master/gui/resource-types")
        assert "GUI Test Resource Type" in type_listing.text
        assert "Vehicle" in type_listing.text

        capability_listing = client.get("/central-master/gui/resource-capabilities")
        assert "GUI Test Capability" in capability_listing.text
    finally:
        _clear_resource_types()


def test_personnel_delete_removes_record(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_personnel()
    try:
        created = client.post(
            "/central-master/gui/personnel/new",
            data={"name": "GUI Test Delete Person"},
        )
        assert created.status_code == 303

        from sarapp_db.api.routers.personnel import list_personnel

        doc = next(d for d in list_personnel(search="", limit=200) if d["name"] == "GUI Test Delete Person")
        record_id = doc["person_record_master"]

        edit_page = client.get(f"/central-master/gui/personnel/{record_id}")
        assert "Delete" in edit_page.text

        deleted = client.post(f"/central-master/gui/personnel/{record_id}/delete")
        assert deleted.status_code == 303

        remaining = [d for d in list_personnel(search="", limit=200) if d["name"] == "GUI Test Delete Person"]
        assert remaining == []
    finally:
        _clear_personnel()


def test_personnel_export_csv_contains_record(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_personnel()
    try:
        client.post(
            "/central-master/gui/personnel/new",
            data={"name": "GUI Test Export Person", "callsign": "Echo-1"},
        )

        response = client.get("/central-master/gui/personnel/export?format=csv")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "GUI Test Export Person" in response.text
        assert "Echo-1" in response.text
        assert "Name" in response.text  # label header, not the raw field key
    finally:
        _clear_personnel()


def test_personnel_export_row_preserves_split_names_and_alternate_fields() -> None:
    from modules.personnel.catalog_io import personnel_export_row

    row = personnel_export_row(
        {
            "personnel_id": "P-77",
            "full_name": "Taylor Morgan",
            "medic": True,
            "certs": [{"certification_type_id": 2003, "level": 2}],
        },
        {2003: {"code": "EMT", "name": "Emergency Medical Technician"}},
    )

    assert row["person_id"] == "P-77"
    assert row["first_name"] == "Taylor"
    assert row["last_name"] == "Morgan"
    assert row["is_medic"] == "Yes"
    assert row["certifications"] == "EMT:2"


def test_personnel_export_xlsx_round_trips_through_import(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_personnel()
    try:
        client.post(
            "/central-master/gui/personnel/new",
            data={"name": "GUI Test Roundtrip Person", "callsign": "Echo-2"},
        )

        exported = client.get("/central-master/gui/personnel/export?format=xlsx")
        assert exported.status_code == 200
        assert exported.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Clear and re-import from the exported file — proves the file is a
        # faithful round trip, not just "some bytes came back".
        from sarapp_db.api.routers.personnel import list_personnel

        _clear_personnel()
        assert list_personnel(search="GUI Test Roundtrip Person", limit=200) == []

        imported = client.post(
            "/central-master/gui/personnel/import",
            files={"file": ("export.xlsx", exported.content, "application/octet-stream")},
        )
        assert imported.status_code == 200
        assert "1" in imported.text  # "1 Personnel imported"

        reimported = list_personnel(search="GUI Test Roundtrip Person", limit=200)
        assert len(reimported) == 1
        assert reimported[0]["callsign"] == "Echo-2"
    finally:
        _clear_personnel()


def test_personnel_import_csv_with_certifications(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_personnel()
    try:
        csv_content = (
            "Name,Primary Role,Certifications\r\n"
            "GUI Test CSV Person,Searcher,EMT:2\r\n"
        )
        imported = client.post(
            "/central-master/gui/personnel/import",
            files={"file": ("people.csv", csv_content.encode("utf-8"), "text/csv")},
        )
        assert imported.status_code == 200
        assert "1" in imported.text

        from sarapp_db.api.routers.personnel import list_personnel

        docs = list_personnel(search="GUI Test CSV Person", limit=200)
        assert len(docs) == 1
        assert docs[0]["certifications"]
    finally:
        _clear_personnel()


def test_equipment_export_and_import_round_trip(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_equipment()
    try:
        client.post(
            "/central-master/gui/equipment/new",
            data={"name": "GUI Test Export Radio", "type": "Radio", "serial_number": "SN-1"},
        )

        exported = client.get("/central-master/gui/equipment/export?format=csv")
        assert exported.status_code == 200
        assert "GUI Test Export Radio" in exported.text
        assert "ID Number" in exported.text

        from sarapp_db.api.routers.equipment import list_equipment

        _clear_equipment()
        assert list_equipment(search="GUI Test Export Radio", limit=200) == []

        imported = client.post(
            "/central-master/gui/equipment/import",
            files={"file": ("equipment.csv", exported.content, "text/csv")},
        )
        assert imported.status_code == 200

        reimported = list_equipment(search="GUI Test Export Radio", limit=200)
        assert len(reimported) == 1
        assert reimported[0]["serial_number"] == "SN-1"
    finally:
        _clear_equipment()


def test_equipment_form_matches_desktop_catalog_fields(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_equipment()
    try:
        created = client.post(
            "/central-master/gui/equipment/new",
            data={
                "name": "GUI Test Field Radio",
                "type": "Radio",
                "id_number": "EQ-1",
                "serial_number": "SN-1",
                "condition": "Serviceable",
                "notes": "Ready",
            },
        )
        assert created.status_code == 303

        from sarapp_db.api.routers.equipment import list_equipment

        doc = next(d for d in list_equipment(search="GUI Test Field Radio", limit=200))
        edit_page = client.get(f"/central-master/gui/equipment/{doc['equipment_record_master']}")

        assert edit_page.status_code == 200
        assert "ID Number" in edit_page.text
        assert "Condition" in edit_page.text
        assert "Ready" in edit_page.text
    finally:
        _clear_equipment()


def test_collection_table_has_search_sort_and_row_edit_link(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_equipment()
    try:
        client.post(
            "/central-master/gui/equipment/new",
            data={"name": "GUI Test Grid Radio", "type": "Radio", "condition": "Serviceable"},
        )

        response = client.get("/central-master/gui/equipment")

        assert response.status_code == 200
        assert 'data-grid-search="grid-equipment"' in response.text
        assert 'class="sortable"' in response.text
        assert 'data-row-href=' in response.text
        assert "Delete All" in response.text
        assert "confirm-dialog" in response.text
        assert "data-confirm-title=" in response.text
        assert "GUI Test Grid Radio" in response.text
    finally:
        _clear_equipment()


def test_vehicle_catalog_create_edit_delete(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_vehicles()
    try:
        created = client.post(
            "/central-master/gui/vehicles/new",
            data={
                "vehicle_id": "GUI Test Vehicle 1",
                "vin": "VIN-1",
                "license_plate": "PLATE-1",
                "year": "2024",
                "make": "Ford",
                "model": "F-150",
                "capacity": "5",
                "type_id": "Utility",
                "status_id": "Available",
                "organization": "GUI Test Org",
                "tags": "truck",
            },
        )
        assert created.status_code == 303
        assert created.headers["location"] == "/central-master/gui/vehicles"

        from sarapp_db.api.routers.vehicles import list_vehicles

        doc = next(
            d for d in list_vehicles(search="GUI Test Vehicle 1", status_filter="", type_filter="")
            if d["vehicle_id"] == "GUI Test Vehicle 1"
        )
        record_id = doc["vehicle_record_master"]
        assert doc["year"] == 2024
        assert doc["capacity"] == 5

        edit_page = client.get(f"/central-master/gui/vehicles/{record_id}")
        assert edit_page.status_code == 200
        assert "License Plate" in edit_page.text
        assert "Resource Type ID" in edit_page.text

        updated = client.post(
            f"/central-master/gui/vehicles/{record_id}",
            data={
                "vehicle_id": "GUI Test Vehicle 1",
                "vin": "VIN-1",
                "license_plate": "PLATE-2",
                "year": "2024",
                "make": "Ford",
                "model": "F-150",
                "capacity": "6",
                "type_id": "Utility",
                "status_id": "In Service",
                "organization": "GUI Test Org",
                "tags": "truck",
            },
        )
        assert updated.status_code == 303

        updated_doc = next(d for d in list_vehicles(search="GUI Test Vehicle 1", status_filter="", type_filter=""))
        assert updated_doc["license_plate"] == "PLATE-2"
        assert updated_doc["capacity"] == 6

        deleted = client.post(f"/central-master/gui/vehicles/{record_id}/delete")
        assert deleted.status_code == 303
        assert list_vehicles(search="GUI Test Vehicle 1", status_filter="", type_filter="") == []
    finally:
        _clear_vehicles()


def test_equipment_delete_removes_record(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_equipment()
    try:
        created = client.post(
            "/central-master/gui/equipment/new",
            data={"name": "GUI Test Radio", "type": "Radio"},
        )
        assert created.status_code == 303

        from sarapp_db.api.routers.equipment import list_equipment

        doc = next(d for d in list_equipment(search="", limit=200) if d["name"] == "GUI Test Radio")
        record_id = doc["equipment_record_master"]

        deleted = client.post(f"/central-master/gui/equipment/{record_id}/delete")
        assert deleted.status_code == 303

        remaining = [d for d in list_equipment(search="", limit=200) if d["name"] == "GUI Test Radio"]
        assert remaining == []
    finally:
        _clear_equipment()


def test_equipment_delete_all_removes_records(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_equipment()
    try:
        client.post("/central-master/gui/equipment/new", data={"name": "GUI Test Radio A", "type": "Radio"})
        client.post("/central-master/gui/equipment/new", data={"name": "GUI Test Radio B", "type": "Radio"})

        deleted = client.post("/central-master/gui/equipment/delete-all")
        assert deleted.status_code == 303

        from sarapp_db.api.routers.equipment import list_equipment

        assert list_equipment(search="GUI Test Radio", limit=200) == []
    finally:
        _clear_equipment()


def test_organization_type_create_edit_delete(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_organization_catalog()
    try:
        created = client.post(
            "/central-master/gui/organization-types/new",
            data={"name": "GUI Test Org Type", "description": "Initial", "sort_order": "42", "is_active": "on"},
        )
        assert created.status_code == 303
        assert created.headers["location"] == "/central-master/gui/organization-types"

        from sarapp_db.api.routers.organizations import list_org_types

        doc = next(d for d in list_org_types(search="GUI Test Org Type") if d["name"] == "GUI Test Org Type")
        record_id = doc["int_id"]
        assert doc["sort_order"] == 42
        assert doc["is_active"] == 1

        updated = client.post(
            f"/central-master/gui/organization-types/{record_id}",
            data={"name": "GUI Test Org Type Updated", "description": "Updated", "sort_order": "43"},
        )
        assert updated.status_code == 303

        updated_doc = next(d for d in list_org_types(search="GUI Test Org Type Updated"))
        assert updated_doc["sort_order"] == 43
        assert updated_doc["is_active"] == 0

        deleted = client.post(f"/central-master/gui/organization-types/{record_id}/delete")
        assert deleted.status_code == 303
        assert list_org_types(search="GUI Test Org Type Updated") == []
    finally:
        _clear_organization_catalog()


def test_organizations_and_ranks_are_importable(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_organization_catalog()
    try:
        client.post(
            "/central-master/gui/rank-structures/new",
            data={"name": "GUI Test Import Structure", "is_active": "on"},
        )

        from sarapp_db.api.routers.organizations import list_organizations, list_rank_structures, list_ranks

        structure = next(d for d in list_rank_structures(search="GUI Test Import Structure"))
        structure_id = structure["int_id"]
        org_csv = (
            "Name,Short Name,Default Rank Structure ID,Active\n"
            f"GUI Test Imported Org,GTIO,{structure_id},Yes\n"
        )
        rank_csv = (
            "Rank Structure ID,Rank Code,Rank Name,Short Display,Sort Order,Active\n"
            f"{structure_id},IMP,GUI Test Imported Rank,IMP,7,Yes\n"
        )

        imported_orgs = client.post(
            "/central-master/gui/organizations/import",
            files={"file": ("organizations.csv", org_csv.encode("utf-8"), "text/csv")},
        )
        imported_ranks = client.post(
            "/central-master/gui/ranks/import",
            files={"file": ("ranks.csv", rank_csv.encode("utf-8"), "text/csv")},
        )

        assert imported_orgs.status_code == 200
        assert imported_ranks.status_code == 200
        assert "1 Organizations imported" in imported_orgs.text
        assert "1 Ranks imported" in imported_ranks.text

        org = next(d for d in list_organizations(search="GUI Test Imported Org"))
        assert org["short_name"] == "GTIO"
        assert org["default_rank_structure_id"] == structure_id

        ranks = list_ranks(structure_id=structure_id, search="GUI Test Imported Rank")
        assert len(ranks) == 1
        assert ranks[0]["sort_order"] == 7
    finally:
        _clear_organization_catalog()


def test_rank_structure_and_rank_are_master_catalog_gui_collections(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_organization_catalog()
    try:
        created_structure = client.post(
            "/central-master/gui/rank-structures/new",
            data={"name": "GUI Test Rank Structure", "description": "Ranks", "sort_order": "5", "is_active": "on"},
        )
        assert created_structure.status_code == 303

        from sarapp_db.api.routers.organizations import list_rank_structures, list_ranks

        structure = next(d for d in list_rank_structures(search="GUI Test Rank Structure"))
        structure_id = structure["int_id"]

        created_rank = client.post(
            "/central-master/gui/ranks/new",
            data={
                "rank_structure_id": str(structure_id),
                "rank_code": "GUI",
                "rank_name": "GUI Test Rank",
                "short_display": "GUI",
                "sort_order": "1",
                "is_active": "on",
            },
        )
        assert created_rank.status_code == 303

        ranks = list_ranks(structure_id=structure_id, search="GUI Test Rank")
        assert len(ranks) == 1
        assert ranks[0]["rank_structure_id"] == structure_id
        assert ranks[0]["sort_order"] == 1
        assert ranks[0]["is_active"] == 1
    finally:
        _clear_organization_catalog()


def test_rank_structure_edit_page_manages_nested_ranks(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_organization_catalog()
    try:
        created_structure = client.post(
            "/central-master/gui/rank-structures/new",
            data={"name": "GUI Test Nested Rank Structure", "description": "Ranks", "is_active": "on"},
        )
        assert created_structure.status_code == 303

        from sarapp_db.api.routers.organizations import list_rank_structures, list_ranks

        structure = next(d for d in list_rank_structures(search="GUI Test Nested Rank Structure"))
        structure_id = structure["int_id"]

        edit_page = client.get(f"/central-master/gui/rank-structures/{structure_id}")
        assert edit_page.status_code == 200
        assert "Ranks In This Structure" in edit_page.text
        assert f"/central-master/gui/rank-structures/{structure_id}/ranks" in edit_page.text
        assert 'type="number" step="1" name="sort_order_0"' in edit_page.text

        saved = client.post(
            f"/central-master/gui/rank-structures/{structure_id}/ranks",
            data={
                "row_count": "1",
                "rank_id_0": "",
                "rank_code_0": "CAP",
                "rank_name_0": "GUI Test Captain",
                "short_display_0": "Capt",
                "sort_order_0": "10",
                "is_active_0": "on",
            },
        )
        assert saved.status_code == 303

        ranks = list_ranks(structure_id=structure_id, search="GUI Test Captain")
        assert len(ranks) == 1
        assert ranks[0]["rank_code"] == "CAP"
        assert ranks[0]["sort_order"] == 10

        rank_id = ranks[0]["int_id"]
        deleted = client.post(
            f"/central-master/gui/rank-structures/{structure_id}/ranks",
            data={
                "row_count": "1",
                "rank_id_0": str(rank_id),
                "rank_code_0": "CAP",
                "rank_name_0": "GUI Test Captain",
                "short_display_0": "Capt",
                "sort_order_0": "10",
                "is_active_0": "on",
                "delete_0": "on",
            },
        )
        assert deleted.status_code == 303
        assert list_ranks(structure_id=structure_id, search="GUI Test Captain") == []
    finally:
        _clear_organization_catalog()


def test_master_catalog_seed_csvs_are_uploadable(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_seed_catalog_rows()
    seed_dir = pathlib.Path(__file__).resolve().parents[2] / "data" / "master_catalog_seed"
    try:
        for route, filename in [
            ("/central-master/gui/organization-types/import", "organization_types.csv"),
            ("/central-master/gui/rank-structures/import", "rank_structures.csv"),
            ("/central-master/gui/ranks/import", "ranks.csv"),
        ]:
            data = (seed_dir / filename).read_bytes()
            response = client.post(route, files={"file": (filename, data, "text/csv")})
            assert response.status_code == 200
            assert "error(s)" not in response.text

        from sarapp_db.api.routers.organizations import list_org_types, list_rank_structures, list_ranks

        assert any(row["name"] == "Fire/Rescue" for row in list_org_types(search="Fire/Rescue"))
        fire_structure = next(row for row in list_rank_structures(search="Fire Department"))
        ranks = list_ranks(structure_id=fire_structure["int_id"], search="Firefighter")
        assert len(ranks) == 1
        assert ranks[0]["rank_code"] == "FF"

        cap_structure = next(row for row in list_rank_structures(search="Civil Air Patrol"))
        cadet_ranks = list_ranks(structure_id=cap_structure["int_id"], search="Cadet Airman Basic")
        assert len(cadet_ranks) == 1
        assert cadet_ranks[0]["rank_code"] == "C/AB"

        senior_ranks = list_ranks(structure_id=cap_structure["int_id"], search="Colonel")
        assert any(r["rank_code"] == "COL" for r in senior_ranks)
        assert any(r["rank_code"] == "C/COL" for r in senior_ranks)
    finally:
        _clear_seed_catalog_rows()


def test_console_user_can_be_created_and_used_for_login(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_console_users()
    try:
        new_page = client.get("/central-master/gui/console-users/new")
        assert new_page.status_code == 200
        assert 'type="password" name="password"' in new_page.text

        created = client.post(
            "/central-master/gui/console-users/new",
            data={
                "username": "gui-test-user",
                "password": "user-secret",
                "is_active": "on",
                "notes": "created by test",
            },
        )
        assert created.status_code == 303

        login_client = _client(monkeypatch)
        login = login_client.post(
            "/central-master/gui/login",
            data={"username": "gui-test-user", "password": "user-secret"},
        )

        assert login.status_code == 303
        assert login.headers["location"] == "/central-master/gui"
    finally:
        _clear_console_users()
