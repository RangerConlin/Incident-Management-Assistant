"""Client-side access to the synchronized Team Type Catalog."""
from __future__ import annotations

import logging
import time

from modules.common.models.lookup_models import ApiTeamTypesRepository

log = logging.getLogger(__name__)
_cached_active: list[dict] | None = None
_cached_at = 0.0


def active_team_types() -> list[dict]:
    global _cached_active, _cached_at
    if _cached_active is not None and time.monotonic() - _cached_at < 30:
        return [dict(row) for row in _cached_active]
    try:
        rows = ApiTeamTypesRepository().list(include_inactive=False)
        if rows:
            _cached_active = sorted(
                rows, key=lambda row: (str(row.get("category") or ""), str(row.get("name") or ""))
            )
            _cached_at = time.monotonic()
            return [dict(row) for row in _cached_active]
    except Exception:
        log.exception("Unable to load the Team Type Catalog")
    _cached_active = []
    _cached_at = time.monotonic()
    return []


def refresh_team_types() -> None:
    global _cached_active, _cached_at
    _cached_active = None
    _cached_at = 0.0


def team_type_by_code(code: object) -> dict:
    target = str(code or "").strip().upper()
    return next((row for row in active_team_types() if str(row.get("type_short") or "").upper() == target), {})
