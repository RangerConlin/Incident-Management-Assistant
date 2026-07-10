"""Env-var-backed tuning constants for the cloud router.

All values are read once at import time from the environment (same pattern
as ``SARAPP_CLOUD_ROUTER_TOKEN``), so operators can tune router behavior via
``docker-compose.yml``/deployment env vars without a code change. See
``Design Documents/Instructions/cloud_router_architecture.md`` for what each
value governs.
"""

from __future__ import annotations

import os


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


REQUEST_TIMEOUT_SECONDS = _float_env("SARAPP_ROUTER_REQUEST_TIMEOUT_SECONDS", 30.0)
HEARTBEAT_INTERVAL_SECONDS = _float_env("SARAPP_ROUTER_HEARTBEAT_INTERVAL_SECONDS", 15.0)
HEARTBEAT_TIMEOUT_SECONDS = _float_env("SARAPP_ROUTER_HEARTBEAT_TIMEOUT_SECONDS", 45.0)
MAX_PENDING_REQUESTS_PER_TUNNEL = _int_env("SARAPP_ROUTER_MAX_PENDING_REQUESTS", 200)
MAX_WS_CHANNELS_PER_TUNNEL = _int_env("SARAPP_ROUTER_MAX_WS_CHANNELS", 100)
MAX_REQUEST_BODY_BYTES = _int_env("SARAPP_ROUTER_MAX_BODY_BYTES", 20 * 1024 * 1024)
REGISTER_RATE_LIMIT_PER_MINUTE = _int_env("SARAPP_ROUTER_REGISTER_RATE_LIMIT", 10)
