"""Command-line entry point for starting a local SARApp incident server."""

from __future__ import annotations

import argparse
from pathlib import Path
import signal
import sys


def _ensure_repo_packages_on_path() -> None:
    """Allow local runs without requiring editable installs first.

    Only ``data/db`` is added here — it is the canonical ``sarapp_db``
    package. ``cloud_server`` ships its own standalone copy of ``sarapp_db``
    for Docker deployment; it must never take priority over the canonical
    package for the local desktop server, so it is intentionally excluded.
    """
    repo_root = Path(__file__).resolve().parent
    package_root = repo_root / "data" / "db"
    package_root_str = str(package_root)
    if package_root.exists():
        sys.path = [p for p in sys.path if p != package_root_str]
        sys.path.insert(0, package_root_str)


_ensure_repo_packages_on_path()

from core.networking.server_info import DEFAULT_LOCAL_SERVER_NAME, DEFAULT_SERVER_PORT
from server.server_manager import SARAppServerManager

DEFAULT_SERVER_HOST = "0.0.0.0"


def main() -> None:
    parser = argparse.ArgumentParser(description="Start a local SARApp incident server")
    parser.add_argument("--host", default=DEFAULT_SERVER_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_SERVER_PORT)
    parser.add_argument("--name", default=DEFAULT_LOCAL_SERVER_NAME)
    args = parser.parse_args()

    manager = SARAppServerManager(host=args.host, port=args.port, server_name=args.name)

    def _handle_signal(sig, frame):
        manager.shutdown()

    signal.signal(signal.SIGINT, _handle_signal)
    try:
        signal.signal(signal.SIGTERM, _handle_signal)
    except (OSError, ValueError):
        pass  # SIGTERM not supported on Windows

    manager.serve_forever()


if __name__ == "__main__":
    main()
