from __future__ import annotations

import ssl

from core.networking import (
    DEFAULT_CLOUD_CONNECT_CODE,
    DEFAULT_CLOUD_ROUTER_URL,
    ConnectionManager,
    resolve_cloud_url,
)
from core.networking.tls import system_ssl_context


def test_empty_cloud_settings_use_working_router_and_connect_code() -> None:
    assert resolve_cloud_url() == (
        f"{DEFAULT_CLOUD_ROUTER_URL}/r/{DEFAULT_CLOUD_CONNECT_CODE}"
    )


def test_environment_cloud_url_remains_the_highest_priority() -> None:
    assert (
        resolve_cloud_url(
            environment_url="https://override.example/r/OVERRIDE-1/",
            configured_url="https://saved.example",
            configured_connect_code="SAVED-1",
        )
        == "https://override.example/r/OVERRIDE-1"
    )


def test_custom_url_without_code_remains_a_direct_target() -> None:
    assert (
        resolve_cloud_url(
            configured_url="https://direct.example",
            configured_connect_code="",
        )
        == "https://direct.example"
    )


def test_health_check_uses_verified_system_tls_context(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _Response:
        status_code = 200

    def _get(url: str, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return _Response()

    monkeypatch.setattr("core.networking.connection_manager.httpx.get", _get)
    manager = ConnectionManager(cloud_url="https://router.example/r/CODE-1")

    assert manager._check_server_health(manager.cloud_url)
    assert captured["url"] == "https://router.example/r/CODE-1/health"
    assert captured["verify"] is system_ssl_context()
    assert isinstance(captured["verify"], ssl.SSLContext)
    assert captured["verify"].verify_mode == ssl.CERT_REQUIRED
    assert captured["verify"].check_hostname is True
