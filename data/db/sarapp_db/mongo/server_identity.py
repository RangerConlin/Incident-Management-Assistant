"""Identifies which server process is running, for fields that need to
record provenance (e.g. ``master_link.master_server_origin``).

Every runtime (lan_server, cloud_server, the built-in offline server) is
free to set ``SARAPP_SERVER_ID`` in its environment the same way it sets
``SARAPP_MONGO_URI`` — a deployment-level setting, never hardcoded. When
unset, this falls back to a hostname-derived id so the value is still
stable across restarts of the same machine, just not guaranteed unique
across a fresh install.
"""

from __future__ import annotations

import os
import socket

_SERVER_ID_ENV_VAR = "SARAPP_SERVER_ID"


def get_server_id() -> str:
    """Return a stable identifier for the server process this code runs in."""
    server_id = os.environ.get(_SERVER_ID_ENV_VAR, "").strip()
    if server_id:
        return server_id
    return f"sarapp-server-{socket.gethostname()}"
