from __future__ import annotations

import sys
from importlib import reload
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from utils.state import AppState


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKIN_DATA_DIR", str(tmp_path))
    from modules.safety.orm import api, repository, service

    reload(repository)
    reload(service)
    reload(api)
    AppState.set_active_incident(2001)
    AppState.set_active_user_id(77)
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


def test_lazy_create_form(client):
    resp = client.get("/api/safety/orm/form", params={"incident_id": 2001, "op": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["incident_id"] == 2001
    assert body["op_period"] == 1


def test_hazard_crud_and_policy(client):
    base = {
        "incident_id": 2001,
        "op_period": 2,
        "sub_activity": "Test",
        "hazard_outcome": "Outcome",
        "initial_risk": "M",
        "control_text": "Controls",
        "residual_risk": "M",
    }
    create = client.post("/api/safety/orm/hazards", json=base)
    assert create.status_code == 201

    hazards = client.get(
        "/api/safety/orm/hazards", params={"incident_id": 2001, "op": 2}
    ).json()
    assert len(hazards) == 1

    high_payload = dict(base)
    high_payload["residual_risk"] = "H"
    high_resp = client.post("/api/safety/orm/hazards", json=high_payload)
    assert high_resp.status_code == 201
    high_id = high_resp.json()["id"]

    blocked = client.post(
        "/api/safety/orm/approve",
        json={"incident_id": 2001, "op_period": 2},
    )
    assert blocked.status_code == 422
    assert blocked.json()["error"] == "approval_blocked"

    high_payload["residual_risk"] = "M"
    update = client.put(
        f"/api/safety/orm/hazards/{high_id}",
        params={"incident_id": 2001, "op": 2},
        json=high_payload,
    )
    assert update.status_code == 200

    approve = client.post(
        "/api/safety/orm/approve",
        json={"incident_id": 2001, "op_period": 2},
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"
