from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.ui_customization.api import router, get_repo
from modules.ui_customization.repository import UICustomizationRepository


@contextmanager
def build_app(storage_path) -> Iterator[tuple[FastAPI, UICustomizationRepository, TestClient]]:
    repo = UICustomizationRepository(storage_path)
    app = FastAPI()
    app.dependency_overrides[get_repo] = lambda: repo
    app.include_router(router)
    with TestClient(app) as client:
        yield app, repo, client


def test_layout_and_theme_endpoints(tmp_path):
    with build_app(tmp_path / "store.json") as (_, repo, client):
        res = client.post(
            "/api/ui/customization/layouts",
            json={
                "name": "Ops",
                "perspective_name": "ops",
                "ads_state": "c3RhdGU=",
                "dashboard_widgets": ["incidentinfo"],
            },
        )
        res.raise_for_status()
        layout_id = res.json()["id"]

        client.post(f"/api/ui/customization/layouts/{layout_id}/activate").raise_for_status()
        assert repo.active_layout_id() == layout_id

        res = client.post(
            "/api/ui/customization/themes",
            json={
                "name": "Mission Dark",
                "base_theme": "dark",
                "tokens": {"bg_window": "#101010"},
            },
        )
        res.raise_for_status()
        theme_id = res.json()["id"]
        client.post(f"/api/ui/customization/themes/{theme_id}/activate").raise_for_status()
        assert repo.active_theme_id() == theme_id

        export_res = client.get("/api/ui/customization/bundle/export")
        export_res.raise_for_status()
        payload = export_res.json()
        assert payload["active_layout_id"] == layout_id
        assert payload["layouts"][0]["id"] == layout_id

        # Import the payload again to ensure endpoint accepts round-trips
        client.post("/api/ui/customization/bundle/import", json=payload).raise_for_status()
        assert len(repo.list_layouts()) >= 1
        assert len(repo.list_themes()) >= 1
