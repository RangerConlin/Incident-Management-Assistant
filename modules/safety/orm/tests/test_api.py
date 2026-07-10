from __future__ import annotations


def _payload(title: str, **overrides):
    payload = {
        "title": title,
        "description": "Test description",
        "category": "Terrain",
        "op_period_ids": [2],
        "location_text": "Division A",
        "control_measure": "Use trekking poles",
        "spe_initial": {"severity": 4, "probability": 3, "exposure": 4},
        "spe_residual": {"severity": 3, "probability": 2, "exposure": 3},
    }
    payload.update(overrides)
    return payload


def test_create_and_list_hazard(orm_app_client):
    created = orm_app_client.post(
        "/api/incidents/2001/safety/hazards", json=_payload("Night travel")
    )
    assert created["title"] == "Night travel"
    assert created["spe_initial"]["score"] == 48
    assert created["spe_initial"]["band"] == "Substantial"
    assert created["spe_residual"]["score"] == 18
    assert created["spe_residual"]["band"] == "Slight"

    hazards = orm_app_client.get(
        "/api/incidents/2001/safety/hazards", params={"op_period": 2}
    )
    assert any(h["id"] == created["id"] for h in hazards)


def test_get_hazard_by_id(orm_app_client):
    created = orm_app_client.post(
        "/api/incidents/2001/safety/hazards", json=_payload("Swift water")
    )
    fetched = orm_app_client.get(f"/api/incidents/2001/safety/hazards/{created['id']}")
    assert fetched["title"] == "Swift water"


def test_patch_hazard_is_partial(orm_app_client):
    created = orm_app_client.post(
        "/api/incidents/2001/safety/hazards", json=_payload("Heat exposure")
    )
    updated = orm_app_client.patch(
        f"/api/incidents/2001/safety/hazards/{created['id']}",
        json={"notes": "Monitoring closely"},
    )
    assert updated["notes"] == "Monitoring closely"
    # Untouched fields survive the partial update.
    assert updated["title"] == "Heat exposure"
    assert updated["spe_initial"]["score"] == created["spe_initial"]["score"]


def test_patch_hazard_updates_spe(orm_app_client):
    created = orm_app_client.post(
        "/api/incidents/2001/safety/hazards", json=_payload("Limited radio coverage")
    )
    updated = orm_app_client.patch(
        f"/api/incidents/2001/safety/hazards/{created['id']}",
        json={"spe_residual": {"severity": 1, "probability": 1, "exposure": 1}},
    )
    assert updated["spe_residual"]["score"] == 1
    assert updated["spe_residual"]["band"] == "Slight"


def test_delete_hazard_removes_from_list(orm_app_client):
    created = orm_app_client.post(
        "/api/incidents/2001/safety/hazards", json=_payload("Vehicle movement near runners")
    )
    orm_app_client.delete(f"/api/incidents/2001/safety/hazards/{created['id']}")
    hazards = orm_app_client.get(
        "/api/incidents/2001/safety/hazards", params={"op_period": 2}
    )
    assert all(h["id"] != created["id"] for h in hazards)


def test_links_round_trip(orm_app_client):
    payload = _payload(
        "Linked hazard",
        links={"work_assignment_ids": [4], "team_ids": [7], "task_ids": []},
    )
    created = orm_app_client.post("/api/incidents/2001/safety/hazards", json=payload)
    assert created["links"]["work_assignment_ids"] == [4]
    assert created["links"]["team_ids"] == [7]

    filtered = orm_app_client.get(
        "/api/incidents/2001/safety/hazards", params={"work_assignment_id": 4}
    )
    assert any(h["id"] == created["id"] for h in filtered)
