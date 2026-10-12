from __future__ import annotations

from utils.catalog_cache import CatalogCache


def test_catalog_cache_memoizes_and_invalidates() -> None:
    cache = CatalogCache(default_ttl_seconds=60)
    calls: list[int] = []

    def loader() -> list[dict[str, int]]:
        calls.append(1)
        return [{"id": len(calls)}]

    first = cache.get("resource_types", "/api/resource-types", loader=loader)
    second = cache.get("resource_types", "/api/resource-types", loader=loader)

    assert first == [{"id": 1}]
    assert second == [{"id": 1}]
    assert len(calls) == 1

    cache.invalidate(name="resource_types")
    third = cache.get("resource_types", "/api/resource-types", loader=loader)

    assert third == [{"id": 2}]
    assert len(calls) == 2
