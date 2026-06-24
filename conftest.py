"""Repo-wide pytest fixtures.

Keep this file minimal — it loads for every test in the suite.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _stop_incident_cache_ws_after_test():
    """Tear down any IncidentCache WebSocket client a test left running.

    Any test that calls AppState.set_active_incident(...) — which is most of
    the suite, per CLAUDE.md's testing guidance — starts a background
    IncidentWebSocketClient thread via utils.incident_cache_loader. That
    thread retries its connection every few seconds forever; nothing in the
    suite ever stops it. Connection refusals fail fast so this hasn't caused
    visible slowdowns yet, but threads were accumulating for the life of the
    test process with no way to clean them up. Stop it after every test
    regardless of whether the test imported incident_cache_loader itself.
    """
    yield
    from utils import incident_cache_loader

    incident_cache_loader.activate_incident(None)
