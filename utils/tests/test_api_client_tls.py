from __future__ import annotations

import logging
import ssl

import httpx

from core.networking.tls import system_ssl_context
from utils import api_client as api_client_module
from utils.catalog_cache import CatalogCache


def test_api_client_uses_verified_system_tls_context(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeClient:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def close(self) -> None:
            pass

    monkeypatch.setattr(api_client_module.httpx, "Client", _FakeClient)

    api_client_module._APIClient()

    context = captured["verify"]
    assert context is system_ssl_context()
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_api_client_logs_request_and_decode_timings(monkeypatch, caplog) -> None:
    client = api_client_module._APIClient.__new__(api_client_module._APIClient)
    client._base_url = "http://testserver"
    monkeypatch.setattr(
        client,
        "_request_with_retry",
        lambda *_args, **_kwargs: httpx.Response(200, json={"ok": True}),
    )

    with caplog.at_level(logging.DEBUG, logger="utils.api_client"):
        assert client.get("/api/test") == {"ok": True}

    message = caplog.messages[-1]
    assert "API GET /api/test" in message
    assert "request" in message
    assert "decode" in message
    assert "status 200" in message


def test_successful_sync_trigger_resync_invalidates_catalog_cache(monkeypatch) -> None:
    test_cache = CatalogCache(default_ttl_seconds=60)
    calls: list[int] = []
    test_cache.get("organizations", "/api/master/organizations", loader=lambda: calls.append(1) or [{"id": 1}])

    client = api_client_module._APIClient.__new__(api_client_module._APIClient)
    client._base_url = "http://testserver"
    monkeypatch.setattr(
        client,
        "_request_with_retry",
        lambda *_args, **_kwargs: httpx.Response(200, json={"synced": True}),
    )
    monkeypatch.setattr("utils.catalog_cache.catalog_cache", test_cache)

    assert client.post("/api/sync-trigger/resync") == {"synced": True}

    test_cache.get("organizations", "/api/master/organizations", loader=lambda: calls.append(1) or [{"id": 2}])
    assert len(calls) == 2


def test_unsynced_sync_trigger_resync_keeps_catalog_cache(monkeypatch) -> None:
    test_cache = CatalogCache(default_ttl_seconds=60)
    calls: list[int] = []
    test_cache.get("organizations", "/api/master/organizations", loader=lambda: calls.append(1) or [{"id": 1}])

    client = api_client_module._APIClient.__new__(api_client_module._APIClient)
    client._base_url = "http://testserver"
    monkeypatch.setattr(
        client,
        "_request_with_retry",
        lambda *_args, **_kwargs: httpx.Response(200, json={"synced": False}),
    )
    monkeypatch.setattr("utils.catalog_cache.catalog_cache", test_cache)

    assert client.post("/api/sync-trigger/resync") == {"synced": False}

    test_cache.get("organizations", "/api/master/organizations", loader=lambda: calls.append(1) or [{"id": 2}])
    assert calls == [1]
