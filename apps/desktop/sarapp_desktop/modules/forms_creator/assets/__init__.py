"""Asset utilities for the form creator module."""

from __future__ import annotations

from pathlib import Path


_ASSET_ROOT = Path(__file__).resolve().parent


def get_asset_path(name: str) -> Path:
    """Return the absolute path to an asset bundled with the module."""

    return _ASSET_ROOT / name
