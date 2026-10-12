"""Startup helpers for running LAN server entrypoints as scripts."""

from __future__ import annotations

from pathlib import Path
import sys


def ensure_repo_root_on_path() -> None:
    """Allow scripts run from inside services/lan_server/ to resolve package imports."""

    repo_root = Path(__file__).resolve().parents[2]
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
    sarapp_db_root = repo_root / "server" / "sarapp_db"
    sarapp_db_root_str = str(sarapp_db_root)
    if sarapp_db_root.exists() and sarapp_db_root_str not in sys.path:
        sys.path.insert(0, sarapp_db_root_str)

