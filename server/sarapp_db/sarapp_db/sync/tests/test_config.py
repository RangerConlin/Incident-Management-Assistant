"""Coverage for sarapp_db.sync.config.derive_central_master_url — the
central catalog lives inside cloud_router itself (mounted at
`/central-master` on the same app that serves `/tunnel/register`), so a
server derives its central-sync endpoint from the tunnel URL it already
has rather than being given a second one.
"""
from __future__ import annotations

import pytest

from sarapp_db.sync.config import derive_central_master_url


@pytest.mark.parametrize(
    "cloud_router_url, expected",
    [
        ("wss://cloud-router.example/tunnel/register", "https://cloud-router.example/central-master"),
        ("ws://localhost:8080/tunnel/register", "http://localhost:8080/central-master"),
        ("wss://cloud-router.example:8443/tunnel/register", "https://cloud-router.example:8443/central-master"),
        (None, ""),
        ("", ""),
    ],
)
def test_derive_central_master_url(cloud_router_url, expected):
    assert derive_central_master_url(cloud_router_url) == expected
