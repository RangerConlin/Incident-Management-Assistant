"""Thin HTTP client for talking to cloud_router's central-master sync API
(`data/db/sarapp_db/api/routers/sync.py`, mounted only in `create_app(mode=
"master_only")`). A server dials out to it the same way `lan_server/
cloud_tunnel_client.py` already dials out to register a tunnel — this is a
plain outbound HTTPS call, not routed through the reverse tunnel itself
(the tunnel carries inbound field-device traffic the other direction).
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 10.0

# Tests substitute an httpx.ASGITransport bound directly to a FastAPI app
# here, rather than spinning up a real uvicorn server/port, so the sync
# relay can be exercised end to end without a network hop. Production code
# never sets this — it's a module-level test seam, not a parameter every
# call site needs to thread through.
_test_transport: Optional[httpx.BaseTransport] = None


def _client() -> httpx.Client:
    return httpx.Client(transport=_test_transport, timeout=_TIMEOUT_SECONDS)


def push_one(base_url: str, token: str, *, collection: str, doc: dict) -> bool:
    """Push one changed document to the central database. Returns True on
    success, False on any failure (network, auth, server error) — callers
    queue a failed push for retry rather than raising."""
    client = _client()
    try:
        response = client.post(
            f"{base_url}/api/sync/push",
            json={"collection": collection, "doc": doc},
            headers={"x-sarapp-sync-token": token},
        )
        response.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        logger.warning("Central sync push failed for %s: %s", collection, exc)
        return False
    finally:
        client.close()


def push_delete(base_url: str, token: str, *, collection: str, doc_id: str, deleted_at: str) -> bool:
    """Push a deletion to the central database as a tombstone. Same
    True/False success contract as `push_one`."""
    client = _client()
    try:
        response = client.post(
            f"{base_url}/api/sync/push",
            json={"collection": collection, "op": "delete", "doc_id": doc_id, "updated_at": deleted_at},
            headers={"x-sarapp-sync-token": token},
        )
        response.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        logger.warning("Central sync delete-push failed for %s: %s", collection, exc)
        return False
    finally:
        client.close()


def pull_since(base_url: str, token: str, *, collection: str, since: str | None) -> list[dict] | None:
    """Return documents the central database has changed since `since` (an
    ISO timestamp, or None for "everything"), or None on failure."""
    client = _client()
    try:
        response = client.get(
            f"{base_url}/api/sync/pull",
            params={"collection": collection, "since": since or ""},
            headers={"x-sarapp-sync-token": token},
        )
        response.raise_for_status()
        return response.json().get("docs", [])
    except httpx.HTTPError as exc:
        logger.warning("Central sync pull failed for %s: %s", collection, exc)
        return None
    finally:
        client.close()
