"""Master radio channel catalog + incident channel plan join.

Mirrors the server-side join in `data/db/sarapp_db/api/routers/communications.py`
(`_map_master_channel`/`_map_incident_channel`) so pickers and comms
enrichment (task comms, channels-plan) can read it without a round trip:

- The master radio channel catalog is admin-managed, shared across every
  incident, and rarely changes mid-incident, so it's a CatalogCache
  candidate rather than IncidentCache.
- The incident's channel plan (`incident_channels`) is incident-scoped and
  already available generically through IncidentCache.

Callers that write to the master catalog must call
`invalidate_master_channels()` afterward so the join doesn't serve stale
channel data for the rest of its TTL.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from utils.catalog_cache import catalog_cache

_CATALOG_NAME = "radio_channels"
_CATALOG_PATH = "/api/comms/master-channels"


def get_master_channels_by_id(*, ttl_seconds: int = 300) -> Dict[int, Dict[str, Any]]:
    """Return ``{master_channel_id: mapped_master_channel_dict}``, memoized
    via CatalogCache. The `/master-channels` endpoint already returns
    server-mapped dicts (see `_map_master_channel`), so no client-side
    remapping is needed here — just index by id."""
    channels = catalog_cache.get(_CATALOG_NAME, _CATALOG_PATH, ttl_seconds=ttl_seconds) or []
    result: Dict[int, Dict[str, Any]] = {}
    for ch in channels:
        cid = ch.get("id")
        if cid is not None:
            result[int(cid)] = ch
    return result


def invalidate_master_channels() -> None:
    """Call after creating/editing/deleting a master radio channel."""
    catalog_cache.invalidate(_CATALOG_NAME)


def _channel_int_id(channel_id: Any) -> Optional[int]:
    """Mirror communications.py's `_channel_int_id`."""
    try:
        return int(str(channel_id).split("-CH-")[-1])
    except (ValueError, IndexError):
        return None


def map_incident_channel(doc: Dict[str, Any], master_by_id: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
    """Mirror communications.py's `_map_incident_channel` server-side join."""
    master_id = doc.get("master_id")
    master: Dict[str, Any] = {}
    if master_id is not None:
        try:
            master = master_by_id.get(int(master_id)) or {}
        except (TypeError, ValueError):
            master = {}
    return {
        "id": _channel_int_id(doc.get("channel_id", "")),
        "channel_id": doc.get("channel_id"),
        "master_id": master_id,
        "channel": master.get("name", ""),
        "function": master.get("function"),
        "band": master.get("band"),
        "system": master.get("system"),
        "mode": master.get("mode"),
        "rx_freq": master.get("rx_freq"),
        "tx_freq": master.get("tx_freq"),
        "rx_tone": master.get("rx_tone"),
        "tx_tone": master.get("tx_tone"),
        "line_a": int(bool(master.get("line_a", False))),
        "line_c": int(bool(master.get("line_c", False))),
        "encryption": doc.get("encryption", "None"),
        "assignment_division": doc.get("assignment_division"),
        "assignment_team": doc.get("assignment_team"),
        "priority": doc.get("priority", "Normal"),
        "include_on_205": int(bool(doc.get("include_on_205", True))),
        "remarks": doc.get("remarks"),
        "sort_index": doc.get("sort_index", 1000),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


def cached_channel_plan(incident_id: str) -> Optional[List[Dict[str, Any]]]:
    """Return the incident's mapped channel-plan rows from IncidentCache +
    the CatalogCache-backed master channel catalog, or None if IncidentCache
    isn't loaded for this incident (callers should fall back to the API)."""
    from utils.incident_cache import incident_cache

    if incident_cache.incident_id != str(incident_id):
        return None
    master_by_id = get_master_channels_by_id()
    docs = incident_cache.get_all("incident_channels")
    rows = [map_incident_channel(d, master_by_id) for d in docs]
    rows.sort(key=lambda r: (r.get("sort_index") if r.get("sort_index") is not None else 1000, str(r.get("channel") or "")))
    return rows


__all__ = [
    "get_master_channels_by_id",
    "invalidate_master_channels",
    "map_incident_channel",
    "cached_channel_plan",
]
