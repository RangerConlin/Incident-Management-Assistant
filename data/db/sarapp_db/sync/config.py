"""Env-var config for the central-master sync relay. Unset
`SARAPP_CENTRAL_MASTER_URL` means this server doesn't sync at all —
every function in this package no-ops (or queues locally) rather than
erroring, so sync is purely opt-in per deployment.
"""

from __future__ import annotations

import os

_URL_ENV_VAR = "SARAPP_CENTRAL_MASTER_URL"
_TOKEN_ENV_VAR = "SARAPP_CLOUD_ROUTER_TOKEN"  # same shared secret the tunnel already uses
_INTERVAL_ENV_VAR = "SARAPP_CENTRAL_SYNC_INTERVAL_SECONDS"

DEFAULT_INTERVAL_SECONDS = 60.0

# Collections known to copy fields from a master record are added here one
# at a time as each is verified end to end — see backlog.md.
SYNCABLE_MASTER_COLLECTIONS = (
    "personnel", "equipment", "vehicles", "aircraft",
    "hazard_types", "gar_templates", "canned_comm_entries", "hospitals",
    "objective_templates", "strategy_templates", "radio_channels",
    "safety_analysis_templates",
)


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
