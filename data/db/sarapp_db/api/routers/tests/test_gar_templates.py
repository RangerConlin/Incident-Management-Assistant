"""Tests for the master GAR template library and its scoring engine."""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

import pytest
from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.api.routers.gar_templates import score_selections
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db


def _clear() -> None:
    get_master_db()[MasterCollections.GAR_TEMPLATES].delete_many({"name": {"$regex": "^TEST_"}})


def _sample_template(name: str = "TEST_Template") -> dict:
    return {
        "name": name,
        "source": "Test",
        "description": "",
        "groups": [
            {
                "id": "g1",
                "name": "Group One",
                "rows": [
                    {
                        "id": "r1",
                        "label": "Row One",
                        "options": [
                            {"id": "low", "label": "Low", "points": 0, "no_go": False},
                            {"id": "high", "label": "High", "points": 10, "no_go": False},
                        ],
                    }
                ],
            },
            {
                "id": "g2",
                "name": "Group Two",
                "rows": [
                    {
                        "id": "r2",
                        "label": "Row Two",
                        "options": [
                            {"id": "ok", "label": "OK", "points": 0, "no_go": False},
                            {"id": "stop", "label": "Stop", "points": 20, "no_go": True},
                        ],
                    }
                ],
            },
        ],
        "bands": [
            {"floor": 15, "label": "Red", "required_reviewer": "IC"},
            {"floor": 5, "label": "Amber", "required_reviewer": "Ops Chief"},
            {"floor": 0, "label": "Green", "required_reviewer": "Team Leader"},
        ],
        "active": True,
    }


# ---------------------------------------------------------------------------
# Scoring engine (pure function, no DB)
# ---------------------------------------------------------------------------

def test_score_selections_sums_points_and_picks_band():
    template = _sample_template()
    result = score_selections(
        template, [{"group_id": "g1", "row_id": "r1", "option_id": "low"}, {"group_id": "g2", "row_id": "r2", "option_id": "ok"}]
    )
    assert result["score"] == 0
    assert result["band"] == "Green"
    assert result["required_reviewer"] == "Team Leader"
    assert result["no_go"] is False
    assert len(result["selections"]) == 2
    assert result["selections"][0]["option_label"] == "Low"


def test_score_selections_band_floor_boundaries():
    template = _sample_template()
    # score 10 -> falls in Amber (floor 5), not Red (floor 15)
    result = score_selections(
        template, [{"group_id": "g1", "row_id": "r1", "option_id": "high"}, {"group_id": "g2", "row_id": "r2", "option_id": "ok"}]
    )
    assert result["score"] == 10
    assert result["band"] == "Amber"


def test_score_selections_no_go_overrides_band_regardless_of_score():
    template = _sample_template()
    result = score_selections(
        template, [{"group_id": "g1", "row_id": "r1", "option_id": "low"}, {"group_id": "g2", "row_id": "r2", "option_id": "stop"}]
    )
    assert result["no_go"] is True
    assert result["band"] == "No-Go"
    assert result["required_reviewer"] == "IC"  # top band's reviewer


def test_score_selections_rejects_missing_row():
    template = _sample_template()
    with pytest.raises(ValueError, match="Missing selection"):
        score_selections(template, [{"group_id": "g1", "row_id": "r1", "option_id": "low"}])


def test_score_selections_rejects_unknown_option():
    template = _sample_template()
    with pytest.raises(ValueError, match="Unknown option"):
        score_selections(
            template,
            [
                {"group_id": "g1", "row_id": "r1", "option_id": "nonexistent"},
                {"group_id": "g2", "row_id": "r2", "option_id": "ok"},
            ],
        )


def test_score_selections_rejects_duplicate_row_selection():
    template = _sample_template()
    with pytest.raises(ValueError, match="Duplicate selection"):
        score_selections(
            template,
            [
                {"group_id": "g1", "row_id": "r1", "option_id": "low"},
                {"group_id": "g1", "row_id": "r1", "option_id": "high"},
                {"group_id": "g2", "row_id": "r2", "option_id": "ok"},
            ],
        )


# ---------------------------------------------------------------------------
# Router CRUD
# ---------------------------------------------------------------------------

def test_create_get_and_list_gar_template():
    _clear()
    app = create_app()
    with TestClient(app) as client:
        created = client.post("/api/gar-templates", json=_sample_template())
        assert created.status_code == 201
        body = created.json()
        template_id = body["id"]
        assert body["name"] == "TEST_Template"

        fetched = client.get(f"/api/gar-templates/{template_id}")
        assert fetched.status_code == 200
        assert fetched.json()["groups"][1]["rows"][0]["options"][1]["no_go"] is True

        listed = client.get("/api/gar-templates")
        assert any(t["id"] == template_id for t in listed.json())
    _clear()


def test_create_gar_template_rejects_duplicate_row_ids():
    _clear()
    app = create_app()
    with TestClient(app) as client:
        payload = _sample_template()
        payload["groups"][0]["rows"].append(dict(payload["groups"][0]["rows"][0]))  # duplicate row id "r1"
        res = client.post("/api/gar-templates", json=payload)
        assert res.status_code == 422
    _clear()


def test_clone_gar_template_gets_new_id_and_copy_name():
    _clear()
    app = create_app()
    with TestClient(app) as client:
        created = client.post("/api/gar-templates", json=_sample_template())
        template_id = created.json()["id"]
        cloned = client.post(f"/api/gar-templates/{template_id}/clone")
        assert cloned.status_code == 201
        clone_body = cloned.json()
        assert clone_body["id"] != template_id
        assert clone_body["name"] == "TEST_Template Copy 1"
    _clear()


def test_set_gar_template_active_flag():
    _clear()
    app = create_app()
    with TestClient(app) as client:
        created = client.post("/api/gar-templates", json=_sample_template())
        template_id = created.json()["id"]
        res = client.patch(f"/api/gar-templates/{template_id}/active", json={"active": False})
        assert res.status_code == 200
        assert res.json()["active"] is False

        listed_default = client.get("/api/gar-templates")
        assert all(t["id"] != template_id for t in listed_default.json())
        listed_all = client.get("/api/gar-templates", params={"include_inactive": True})
        assert any(t["id"] == template_id for t in listed_all.json())
    _clear()
