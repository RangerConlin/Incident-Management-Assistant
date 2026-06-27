from __future__ import annotations

"""Read repository for the master communications catalog.

Backed by the SARApp API / MongoDB - see ``ApiMasterRepository`` below.
There used to also be a SQLite-backed ``MasterRepository`` here, kept around
solely because ``traffic_log`` still used a SQLite comms log; now that
traffic_log is Mongo-backed too, nothing references the SQLite catalog
reader and it was removed.
"""

from typing import Any, Dict, List


class ApiMasterRepository:
    """MasterRepository backed by the SARApp API (MongoDB)."""

    def list_channels(self, filters: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        from utils.api_client import api_client
        params = {}
        if filters:
            if filters.get("search"):
                params["search"] = filters["search"]
            if filters.get("band"):
                params["band"] = filters["band"]
            if filters.get("mode"):
                params["mode"] = filters["mode"]
        return api_client.get("/api/comms/master-channels", params=params or None)

    def get_channel(self, channel_id: int) -> Dict[str, Any] | None:
        from utils.api_client import api_client
        try:
            return api_client.get(f"/api/comms/master-channels/{channel_id}")
        except Exception:
            return None

    def create_channel(self, data: Dict[str, Any]) -> Dict[str, Any]:
        from utils.api_client import api_client
        return api_client.post("/api/comms/master-channels", json=data)


__all__ = ["ApiMasterRepository"]
