from __future__ import annotations

import pytest

from modules.personnel.units_organizations.models import repository as repo_module
from utils.api_client import api_client
from utils.catalog_cache import catalog_cache


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.setattr(repo_module, "seed_if_needed", lambda: None)
    catalog_cache.invalidate()
    yield
    catalog_cache.invalidate()


def _repo() -> repo_module.UnitsOrganizationsRepository:
    return repo_module.UnitsOrganizationsRepository()


def test_list_organization_types_is_cached(monkeypatch):
    calls: list[str] = []

    def fake_get(path, params=None):
        calls.append(path)
        return [{"int_id": 1, "name": "Ground SAR"}]

    monkeypatch.setattr(api_client, "get", fake_get)

    repo = _repo()
    first = repo.list_organization_types()
    second = repo.list_organization_types()

    assert first == second
    assert calls == ["/api/master/types"]


def test_create_organization_type_invalidates_cache(monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_get(path, params=None):
        calls.append(("get", path))
        return [{"int_id": 1, "name": "Ground SAR"}]

    def fake_post(path, json=None):
        calls.append(("post", path))
        return {"int_id": 2}

    monkeypatch.setattr(api_client, "get", fake_get)
    monkeypatch.setattr(api_client, "post", fake_post)

    repo = _repo()
    repo.list_organization_types()
    repo.create_organization_type({"name": "New Type"})
    repo.list_organization_types()

    get_calls = [c for c in calls if c[0] == "get"]
    assert len(get_calls) == 2


def test_list_organizations_and_get_organization_are_cached(monkeypatch):
    calls: list[str] = []

    def fake_get(path, params=None):
        calls.append(path)
        if path == "/api/master/organizations":
            return [{"int_id": 5, "name": "Sample Org"}]
        return {"int_id": 5, "name": "Sample Org"}

    monkeypatch.setattr(api_client, "get", fake_get)

    repo = _repo()
    repo.list_organizations()
    repo.list_organizations()
    repo.get_organization(5)
    repo.get_organization(5)

    assert calls == ["/api/master/organizations", "/api/master/organizations/5"]


def test_update_organization_invalidates_cache(monkeypatch):
    calls: list[str] = []

    def fake_get(path, params=None):
        calls.append(("get", path))
        return {"int_id": 5, "name": "Sample Org"}

    def fake_patch(path, json=None):
        calls.append(("patch", path))

    monkeypatch.setattr(api_client, "get", fake_get)
    monkeypatch.setattr(api_client, "patch", fake_patch)

    repo = _repo()
    repo.get_organization(5)
    repo.update_organization(5, {"name": "Renamed"})
    repo.get_organization(5)

    get_calls = [c for c in calls if c[0] == "get"]
    assert len(get_calls) == 2


def test_list_ranks_is_cached_per_structure_and_invalidated_on_replace(monkeypatch):
    calls: list[str] = []

    def fake_get(path, params=None):
        calls.append((path, tuple(sorted((params or {}).items()))))
        return [{"int_id": 1, "rank_structure_id": 10, "rank_code": "FF1", "rank_name": "Firefighter"}]

    def fake_delete(path):
        pass

    def fake_post(path, json=None):
        return {"int_id": 2}

    monkeypatch.setattr(api_client, "get", fake_get)
    monkeypatch.setattr(api_client, "delete", fake_delete)
    monkeypatch.setattr(api_client, "post", fake_post)

    repo = _repo()
    repo.list_ranks(10)
    repo.list_ranks(10)
    repo.replace_ranks(10, [{"rank_code": "FF2", "rank_name": "Firefighter II"}])
    repo.list_ranks(10)

    cached_calls = [c for c in calls if c[0] == "/api/master/ranks"]
    # 1 memoized read + 1 read-before-replace inside replace_ranks (not cached,
    # by design) + 1 re-fetch after invalidation = 3 total GETs.
    assert len(cached_calls) == 3
