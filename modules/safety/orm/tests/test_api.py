from __future__ import annotations


def _payload(title: str, **overrides):
    payload = {
        "title": title,
        "description": "Test description",
        "category": "Terrain",
        "op_period_ids": [2],
        "location_text": "Division A",
        "control_measure": "Use trekking poles",
        "default_spe": {"severity": 4, "probability": 3, "exposure": 4},
        "spe_residual": {"severity": 3, "probability": 2, "exposure": 3},
    }
    payload.update(overrides)
    return payload


def test_create_and_list_hazard(orm_app_client):
    created = orm_app_client.post(
        "/api/incidents/2001/safety/hazards", json=_payload("Night travel")
    )
    assert created["title"] == "Night travel"
    assert created["default_spe"]["score"] == 48
    assert created["default_spe"]["band"] == "Substantial"
    assert created["spe_residual"]["score"] == 18
    assert created["spe_residual"]["band"] == "Slight"

    hazards = orm_app_client.get("/api/incidents/2001/safety/hazards")
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
    assert updated["default_spe"]["score"] == created["default_spe"]["score"]


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
    hazards = orm_app_client.get("/api/incidents/2001/safety/hazards")
    assert all(h["id"] != created["id"] for h in hazards)


def test_create_hazard_starts_with_empty_backend_linkage_lists(orm_app_client):
    created = orm_app_client.post(
        "/api/incidents/2001/safety/hazards", json=_payload("Linked hazard")
    )
    assert created["work_assignment_ids"] == []
    assert created["team_ids"] == []
    assert created["task_ids"] == []
    assert created["hazard_zone_ids"] == []
