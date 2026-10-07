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
