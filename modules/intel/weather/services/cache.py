"""Cache helpers for weather data."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

LOGGER = logging.getLogger(__name__)

_CACHE_DIR = Path("data/cache/weather")
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def cache_path(name: str) -> Path:
    """Return the cache path for the provided name."""

    safe_name = name.replace("/", "_")
    return _CACHE_DIR / f"{safe_name}.json"


def read_cache(name: str) -> Optional[Dict[str, Any]]:
    """Read JSON data from cache."""

    path = cache_path(name)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        LOGGER.warning("Failed to parse cache %s: %s", name, exc)
        return None


def write_cache(name: str, data: Dict[str, Any]) -> None:
    """Persist JSON-serialisable data to cache."""

    path = cache_path(name)
    path.write_text(json.dumps(data), encoding="utf-8")


__all__ = ["read_cache", "write_cache", "cache_path"]
