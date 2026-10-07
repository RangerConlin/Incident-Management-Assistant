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


def test_create_and_edit_personnel_record(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_personnel()
    try:
        created = client.post(
            "/central-master/gui/personnel/new",
            data={"name": "GUI Test Person", "primary_role": "Searcher"},
        )
        assert created.status_code == 303
        assert created.headers["location"] == "/central-master/gui/personnel"

        listing = client.get("/central-master/gui/personnel")
        assert "GUI Test Person" in listing.text

        from sarapp_db.api.routers.personnel import list_personnel

        doc = next(d for d in list_personnel(search="", limit=200) if d["name"] == "GUI Test Person")
        record_id = doc["person_record"]

        edit_page = client.get(f"/central-master/gui/personnel/{record_id}")
        assert edit_page.status_code == 200
        assert "GUI Test Person" in edit_page.text

        updated = client.post(
            f"/central-master/gui/personnel/{record_id}",
            data={"name": "GUI Test Person Updated", "primary_role": "Searcher"},
        )
        assert updated.status_code == 303

        edit_page_after = client.get(f"/central-master/gui/personnel/{record_id}")
        assert "GUI Test Person Updated" in edit_page_after.text
    finally:
        _clear_personnel()


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
        record_id = doc["person_record"]

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


def test_personnel_export_xlsx_round_trips_through_import(monkeypatch) -> None:
    client = _client(monkeypatch)
    _login(client)
    _clear_personnel()
    try:
        client.post(
            "/central-master/gui/personnel/new",
            data={"name": "GUI Test Roundtrip Person", "primary_role": "Medic", "callsign": "Echo-2"},
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
        assert reimported[0]["primary_role"] == "Medic"
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
        record_id = doc["equipment_record"]

        deleted = client.post(f"/central-master/gui/equipment/{record_id}/delete")
        assert deleted.status_code == 303

        remaining = [d for d in list_equipment(search="", limit=200) if d["name"] == "GUI Test Radio"]
        assert remaining == []
    finally:
        _clear_equipment()
