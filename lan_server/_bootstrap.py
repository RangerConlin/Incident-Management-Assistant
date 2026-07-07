"""Startup helpers for running LAN server entrypoints as scripts."""

from __future__ import annotations

from pathlib import Path
import sys


def ensure_repo_root_on_path() -> None:
    """Allow `python server_manager.py` from inside `lan_server/` to resolve package imports."""

    repo_root = Path(__file__).resolve().parents[1]
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)

