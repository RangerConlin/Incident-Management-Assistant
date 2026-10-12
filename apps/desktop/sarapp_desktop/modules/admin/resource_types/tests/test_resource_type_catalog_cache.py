from __future__ import annotations

import pytest

from modules.admin.resource_types.data.resource_type_repository import ApiResourceTypeRepository
from modules.admin.resource_types.models.resource_type_models import ResourceCapability, ResourceType
from utils.api_client import api_client
from utils.catalog_cache import catalog_cache


@pytest.fixture(autouse=True)
def _clear_catalog_cache():
    catalog_cache.invalidate()
    yield
    catalog_cache.invalidate()


def test_list_resource_types_default_view_is_cached(monkeypatch):
    calls: list[str] = []

    def fake_get(path, params=None):
        calls.append(path)
        return [{"resource_type_id": "1", "name": "Type A", "is_active": True}]

    monkeypatch.setattr(api_client, "get", fake_get)

    repo = ApiResourceTypeRepository()
    first = repo.list_resource_types()
    second = repo.list_resource_types()

    assert first == second
    assert len(calls) == 1  # second call served from cache


def test_list_resource_types_with_search_text_bypasses_cache(monkeypatch):
    calls: list[str] = []

    def fake_get(path, params=None):
        calls.append(path)
        return [{"resource_type_id": "1", "name": "Type A"}]

    monkeypatch.setattr(api_client, "get", fake_get)

    repo = ApiResourceTypeRepository()
    repo.list_resource_types(search_text="a")
    repo.list_resource_types(search_text="a")

    assert len(calls) == 2  # live search is never memoized


def test_get_resource_type_is_cached(monkeypatch):
    calls: list[str] = []

    def fake_get(path, params=None):
        calls.append(path)
        return {"resource_type_id": "7", "name": "Engine", "is_active": True}

    monkeypatch.setattr(api_client, "get", fake_get)

    repo = ApiResourceTypeRepository()
    repo.get_resource_type(7)
    repo.get_resource_type(7)

    assert calls == ["/api/resource-types/7"]


def test_save_resource_type_invalidates_the_catalog(monkeypatch):
    calls: list[str] = []

    def fake_get(path, params=None):
        calls.append(("get", path))
        return [{"resource_type_id": "1", "name": "Type A"}]

    def fake_put(path, json=None):
        calls.append(("put", path))
        return {"resource_type_id": "1"}

    monkeypatch.setattr(api_client, "get", fake_get)
    monkeypatch.setattr(api_client, "put", fake_put)

    repo = ApiResourceTypeRepository()
    repo.list_resource_types()
    repo.save_resource_type(ResourceType(id=1, name="Type A"))
    repo.list_resource_types()

    get_calls = [c for c in calls if c[0] == "get"]
    assert len(get_calls) == 2  # cache was invalidated by the save, so it re-fetched


def test_list_capabilities_is_cached_and_invalidated_on_save(monkeypatch):
    calls: list[str] = []

    def fake_get(path, params=None):
        calls.append(("get", path))
        return [{"id": 1, "name": "Water Rescue"}]

    def fake_post(path, json=None):
        calls.append(("post", path))
        return {"id": 2}

    monkeypatch.setattr(api_client, "get", fake_get)
    monkeypatch.setattr(api_client, "post", fake_post)

    repo = ApiResourceTypeRepository()
    repo.list_capabilities()
    repo.list_capabilities()
    repo.save_capability(ResourceCapability(id=None, name="New Capability"))
    repo.list_capabilities()

    get_calls = [c for c in calls if c[0] == "get"]
    assert len(get_calls) == 2  # 1 initial + 1 after invalidation; the memoized repeat didn't re-fetch
