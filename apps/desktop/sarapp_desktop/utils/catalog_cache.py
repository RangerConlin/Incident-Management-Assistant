"""Small in-memory cache for stable master/global lookup API data.

IncidentCache is scoped to the active incident and kept live by WebSocket
events. CatalogCache is simpler: it memoizes mostly-stable lookup endpoints
such as resource types, hazard types, organizations, rank structures, and
radio libraries so every picker/dialog does not re-query the API on open.

Callers should invalidate a key after writing to the matching catalog.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 300


@dataclass(frozen=True)
class CatalogKey:
    """Stable cache key for one API list/detail request."""

    name: str
    path: str
    params: tuple[tuple[str, Any], ...] = ()

    @classmethod
    def from_request(
        cls,
        name: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> "CatalogKey":
        cleaned = tuple(sorted((k, v) for k, v in (params or {}).items() if v is not None))
        return cls(name=name, path=path, params=cleaned)


@dataclass
class _CatalogEntry:
    value: Any
    loaded_at: float
    ttl_seconds: int

    def is_fresh(self, now: float) -> bool:
        return self.ttl_seconds <= 0 or (now - self.loaded_at) < self.ttl_seconds


class CatalogCache:
    """Thread-safe memoizing cache for stable lookup data."""

    def __init__(self, default_ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._default_ttl_seconds = default_ttl_seconds
        self._lock = threading.Lock()
        self._entries: Dict[CatalogKey, _CatalogEntry] = {}

    def get(
        self,
        name: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None,
        loader: Optional[Callable[[], Any]] = None,
    ) -> Any:
        key = CatalogKey.from_request(name, path, params)
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry and entry.is_fresh(now):
                return copy.deepcopy(entry.value)

        if loader is None:
            from utils.api_client import api_client

            loader = lambda: api_client.get(path, params=params if params else None)

        value = loader()
        with self._lock:
            self._entries[key] = _CatalogEntry(
                value=copy.deepcopy(value),
                loaded_at=now,
                ttl_seconds=self._default_ttl_seconds if ttl_seconds is None else int(ttl_seconds),
            )
        return copy.deepcopy(value)

    def invalidate(self, name: Optional[str] = None, path: Optional[str] = None) -> None:
        """Drop entries matching a cache namespace and/or path."""
        with self._lock:
            if name is None and path is None:
                self._entries.clear()
                return
            for key in list(self._entries):
                if name is not None and key.name != name:
                    continue
                if path is not None and key.path != path:
                    continue
                self._entries.pop(key, None)

    def telemetry(self) -> dict[str, Any]:
        with self._lock:
            return {
                "entries": len(self._entries),
                "keys": [
                    {
                        "name": key.name,
                        "path": key.path,
                        "params": dict(key.params),
                    }
                    for key in self._entries
                ],
            }


catalog_cache = CatalogCache()

__all__ = ["CatalogCache", "CatalogKey", "catalog_cache"]
