"""Simple application settings switches used by various modules.

Currently provides a `DEV_MODE` flag that is True when either the
environment variable `SARAPP_DEV=1` is set or a config INI in `data/`
contains a matching key. Defaults to False when unspecified.
"""

from __future__ import annotations

import os
import configparser
from pathlib import Path


def _read_ini_flag() -> bool:
    """Read `DEV_MODE` from `data/app.ini` if present.

    The INI may contain a section `[app]` with `dev = true/false/1/0`.
    """
    data_dir = Path(os.environ.get("CHECKIN_DATA_DIR", "data"))
    ini_path = data_dir / "app.ini"
    if not ini_path.exists():
        return False
    try:
        cp = configparser.ConfigParser()
        cp.read(ini_path)
        raw = cp.get("app", "dev", fallback="0").strip().lower()
        return raw in {"1", "true", "yes", "on"}
    except Exception:
        return False


DEV_MODE: bool = (
    str(os.environ.get("SARAPP_DEV", "0")).strip() in {"1", "true", "True"}
    or _read_ini_flag()
)


__all__ = ["DEV_MODE"]

