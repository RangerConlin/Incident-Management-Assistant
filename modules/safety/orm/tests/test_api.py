from __future__ import annotations


def test_lazy_create_form(orm_app_client):
    resp = orm_app_client.get("/api/incidents/2001/safety/orm/form", params={"op": 1})
    assert resp["incident_id"] == "2001"
    assert resp["op_period"] == 1


def test_form_creation_is_idempotent(orm_app_client):
    """Fetching the same incident/op_period form twice returns the same
    singleton record rather than creating a duplicate — this replaces the
    old SQLite-repository unique-constraint test now that forms are
    upserted via MongoDB instead of inserted directly."""
    first = orm_app_client.get("/api/incidents/2002/safety/orm/form", params={"op": 1})
    second = orm_app_client.get("/api/incidents/2002/safety/orm/form", params={"op": 1})
    assert first["id"] == second["id"]


def test_hazard_crud_and_policy(orm_app_client):
    base = {
        "op_period": 2,
        "sub_activity": "Test",
        "hazard_outcome": "Outcome",
        "initial_risk": "M",
        "control_text": "Controls",
        "residual_risk": "M",
    }
    create = orm_app_client.post("/api/incidents/2001/safety/orm/hazards", json=base)
    assert create["sub_activity"] == "Test"

    hazards = orm_app_client.get("/api/incidents/2001/safety/orm/hazards", params={"op": 2})
    assert len(hazards) >= 1

    high_payload = dict(base)
    high_payload["residual_risk"] = "H"
    high = orm_app_client.post("/api/incidents/2001/safety/orm/hazards", json=high_payload)

    from utils.api_client import APIError

    try:
        orm_app_client.post(
            "/api/incidents/2001/safety/orm/approve",
            json={"op_period": 2},
        )
        assert False, "approval should be blocked while a high-risk hazard is open"
    except APIError as exc:
        assert exc.status_code == 422

    update_payload = {
        "sub_activity": high["sub_activity"],
        "hazard_outcome": high["hazard_outcome"],
        "initial_risk": high["initial_risk"],
        "control_text": high["control_text"],
        "residual_risk": "M",
        "implement_how": high.get("implement_how"),
        "implement_who": high.get("implement_who"),
    }
    updated = orm_app_client.put(
        f"/api/incidents/2001/safety/orm/hazards/{high['id']}",
        params={"op": 2},
        json=update_payload,
    )
    assert updated["residual_risk"] == "M"

    approved = orm_app_client.post(
        "/api/incidents/2001/safety/orm/approve",
        json={"op_period": 2},
    )
    assert approved["status"] == "approved"
