"""Env-var config for the central-master sync relay. Unset
`SARAPP_CENTRAL_MASTER_URL` means this server doesn't sync at all —
every function in this package no-ops (or queues locally) rather than
erroring, so sync is purely opt-in per deployment.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

_URL_ENV_VAR = "SARAPP_CENTRAL_MASTER_URL"
_TOKEN_ENV_VAR = "SARAPP_CLOUD_ROUTER_TOKEN"  # same shared secret the tunnel already uses
_INTERVAL_ENV_VAR = "SARAPP_CENTRAL_SYNC_INTERVAL_SECONDS"

DEFAULT_INTERVAL_SECONDS = 60.0

# Collections known to sync through the central-master relay.
SYNCABLE_MASTER_COLLECTIONS = (
    "personnel", "equipment", "vehicles", "aircraft",
    "hazard_types", "gar_templates", "canned_comm_entries", "hospitals",
    "objective_templates", "strategy_templates", "radio_channels",
    "safety_analysis_templates", "meeting_templates",
    "resource_types", "resource_capabilities",
)

# Collections with a server-local sequential id plus a central agency-wide
# sequential id. The local field is meaningful only inside one server's
# `sarapp_master`; it must never be copied from central into another local
# catalog as-is.
DUAL_KEY_RECORD_FIELDS = {
    "personnel": ("person_record", "person_record_master"),
    "equipment": ("equipment_record", "equipment_record_master"),
    "vehicles": ("vehicle_record", "vehicle_record_master"),
    "aircraft": ("aircraft_record", "aircraft_record_master"),
    "hazard_types": ("id", "id_master"),
    "gar_templates": ("id", "id_master"),
    "canned_comm_entries": ("id", "id_master"),
    "hospitals": ("id", "id_master"),
    "objective_templates": ("int_id", "int_id_master"),
    "strategy_templates": ("int_id", "int_id_master"),
    "radio_channels": ("channel_id", "channel_id_master"),
    "safety_analysis_templates": ("template_id", "template_id_master"),
}


def central_master_url() -> str:
    return os.environ.get(_URL_ENV_VAR, "").strip().rstrip("/")


def sync_token() -> str:
    return os.environ.get(_TOKEN_ENV_VAR, "").strip()


def sync_enabled() -> bool:
    return bool(central_master_url())


def sync_interval_seconds() -> float:
    try:
        return float(os.environ.get(_INTERVAL_ENV_VAR, str(DEFAULT_INTERVAL_SECONDS)))
    except ValueError:
        return DEFAULT_INTERVAL_SECONDS


def derive_central_master_url(cloud_router_url: str | None) -> str:
    """Derive the central-catalog sync endpoint from a tunnel-registration
    URL — the central catalog lives inside cloud_router's own process,
    mounted at `/central-master` on the same app that serves
    `/tunnel/register` (see `services/cloud_router/router/app.py`). A server that
    already knows how to reach cloud_router for its tunnel (LAN server's
    `cloud_router_url` setting, or the hosted cloud server's own tunnel
    config) needs no separate, manually-configured central-catalog URL:
    same host, swap the `ws(s)://` scheme for `http(s)://`, drop the
    `/tunnel/register` path, and add the `/central-master` mount point.

    Returns "" when `cloud_router_url` is empty/unset — no tunnel means no
    central catalog to sync to either.
    """

    if not cloud_router_url:
        return ""
    parsed = urlparse(cloud_router_url)
    if not parsed.netloc:
        return ""
    scheme = "https" if parsed.scheme in ("wss", "https") else "http"
    return f"{scheme}://{parsed.netloc}/central-master"
