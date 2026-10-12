"""Connectivity diagnostics — no incident data, nothing persisted to Mongo.

POST /api/diagnostics/echo — echo back whatever JSON body was sent, plus a
server-side timestamp and server id. Meant to be hit through the cloud
router's tunnel (``/r/<connect_code>/api/diagnostics/echo``) from a mobile
device or curl to prove the full mobile -> cloud router -> LAN server ->
back round trip works, independent of any incident/auth state.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@router.post("/echo")
async def echo(request: Request) -> dict[str, Any]:
    try:
        body: Any = await request.json()
    except Exception:  # noqa: BLE001 - empty/non-JSON body is a valid test call too
        body = None
    return {
        "received": body,
        "server_time_utc": _utcnow(),
        "client_host": request.client.host if request.client else None,
    }


@router.get("/echo")
async def echo_get() -> dict[str, Any]:
    """GET variant so the round trip can be tested from a plain browser tab."""

    return {"received": None, "server_time_utc": _utcnow()}
