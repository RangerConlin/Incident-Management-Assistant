"""Coverage for ServerConsoleSettings validation/persistence — currently
just the existing cloud_router_url/connect_code round trip (central-catalog
sync has no settings field of its own; see
sarapp_db.sync.config.derive_central_master_url, which derives it
automatically from cloud_router_url instead).
"""
from __future__ import annotations

import pytest

from lan_server.server_console.settings import ServerConsoleSettings


@pytest.mark.parametrize("url", ["wss://cloud-router.example/tunnel/register", ""])
def test_valid_cloud_router_url_accepted(url):
    settings = ServerConsoleSettings(cloud_router_url=url)
    settings.validate()  # must not raise


def test_invalid_cloud_router_url_rejected():
    with pytest.raises(ValueError):
        ServerConsoleSettings(cloud_router_url="https://cloud-router.example").validate()


def test_settings_round_trip_through_dict():
    settings = ServerConsoleSettings(cloud_router_url="wss://cloud-router.example/tunnel/register", connect_code="ABCD-1234")
    restored = ServerConsoleSettings.from_dict(settings.to_dict())
    assert restored.cloud_router_url == settings.cloud_router_url
    assert restored.connect_code == settings.connect_code
