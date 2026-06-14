from __future__ import annotations

"""Read-only personnel lookup for organization assignments."""

from typing import Callable, Iterable, Sequence

from utils.db import get_master_conn


class ApiPersonnelPoolRepository:
    """Personnel search backed by the SARApp API (MongoDB)."""

    def search_people(self, query: str, limit: int = 25) -> list[dict]:
        term = query.strip()
        if len(term) < 2:
            return []
        try:
            from utils.api_client import api_client
            results = api_client.get(
                "/api/master/personnel",
                params={"search": term, "limit": limit},
            ) or []
            return [
                {
                    "id": r.get("id"),
                    "name": r.get("name", ""),
                    "callsign": r.get("callsign", ""),
                    "phone": r.get("contact", "") or r.get("phone", ""),
                    "agency": r.get("home_unit", "") or r.get("agency", ""),
                }
                for r in results
            ]
        except Exception:
            return []


