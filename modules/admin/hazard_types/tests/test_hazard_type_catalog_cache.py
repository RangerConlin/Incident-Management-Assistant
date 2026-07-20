from __future__ import annotations

import pytest

from modules.admin.hazard_types.data.hazard_type_repository import (
    ApiHazardTypeRepository,
    ApiSafetyTemplateRepository,
)
from modules.admin.hazard_types.models.hazard_type_models import HazardDefaultSpe, HazardType
from utils.api_client import api_client
from utils.catalog_cache import catalog_cache


@pytest.fixture(autouse=True)
def _clear_catalog_cache():
    catalog_cache.invalidate()
    yield
    catalog_cache.invalidate()


def test_list_hazard_types_default_view_is_cached(monkeypatch):
    calls: list[str] = []

    def fake_get(path, params=None):
        calls.append(path)
        return [{"id": 1, "name": "Flood", "active": True}]

    monkeypatch.setattr(api_client, "get", fake_get)

    repo = ApiHazardTypeRepository()
    first = repo.list_hazard_types()
    second = repo.list_hazard_types()

    assert first == second
    assert len(calls) == 1


def test_list_hazard_types_with_search_text_bypasses_cache(monkeypatch):
    calls: list[str] = []

    def fake_get(path, params=None):
        calls.append(path)
        return [{"id": 1, "name": "Flood"}]

    monkeypatch.setattr(api_client, "get", fake_get)

    repo = ApiHazardTypeRepository()
    repo.list_hazard_types({"search_text": "fl"})
    repo.list_hazard_types({"search_text": "fl"})

    assert len(calls) == 2


def test_get_hazard_type_is_cached(monkeypatch):
    calls: list[str] = []

    def fake_get(path, params=None):
        calls.append(path)
        return {"id": 3, "name": "Lightning", "active": True}

    monkeypatch.setattr(api_client, "get", fake_get)

    repo = ApiHazardTypeRepository()
    repo.get_hazard_type(3)
    repo.get_hazard_type(3)

    assert calls == ["/api/hazard-types/3"]


def test_update_hazard_type_invalidates_the_catalog(monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_get(path, params=None):
        calls.append(("get", path))
        return [{"id": 1, "name": "Flood"}]

    def fake_put(path, json=None):
        calls.append(("put", path))
        return {"id": 1}

    monkeypatch.setattr(api_client, "get", fake_get)
    monkeypatch.setattr(api_client, "put", fake_put)

    repo = ApiHazardTypeRepository()
    repo.list_hazard_types()
    repo.update_hazard_type(
        1,
        HazardType(
            id=1,
            name="Flood",
            default_spe=HazardDefaultSpe(
                severity=1,
                probability=1,
                exposure=1,
                score=1,
                band="Slight",
                action="Possibly Acceptable",
            ),
        ),
    )
    repo.list_hazard_types()

    get_calls = [c for c in calls if c[0] == "get"]
    assert len(get_calls) == 2


def test_list_safety_templates_default_view_is_cached_and_invalidated(monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_get(path, params=None):
        calls.append(("get", path))
        return [{"template_id": 1, "name": "Water Rescue Template"}]

    def fake_post(path, json=None):
        calls.append(("post", path))
        return {"template_id": 2}

    monkeypatch.setattr(api_client, "get", fake_get)
    monkeypatch.setattr(api_client, "post", fake_post)

    repo = ApiSafetyTemplateRepository()
    repo.list_templates()
    repo.list_templates()
    repo.create_template({"name": "New Template"})
    repo.list_templates()

    get_calls = [c for c in calls if c[0] == "get"]
    assert len(get_calls) == 2  # 1 initial + 1 after invalidation
