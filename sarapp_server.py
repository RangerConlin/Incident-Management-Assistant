"""Command-line entry point for starting a local SARApp incident server."""

from __future__ import annotations

import argparse
import threading
from pathlib import Path
import signal
import sys


def _ensure_repo_packages_on_path() -> None:
    """Allow local runs without requiring editable installs first.

    Only ``server/sarapp_db`` is added here — it is the canonical ``sarapp_db``
    package. ``cloud_server`` imports that same package for Docker
    deployment; local desktop runs should keep resolving the canonical package
    from ``server/sarapp_db``.
    """
    repo_root = Path(__file__).resolve().parent
    package_root = repo_root / "server" / "sarapp_db"
    package_root_str = str(package_root)
    if package_root.exists():
        sys.path = [p for p in sys.path if p != package_root_str]
        sys.path.insert(0, package_root_str)

    # Desktop packages (core, services, etc.) now live under
    # apps/desktop/sarapp_desktop; expose them on sys.path by their bare names.
    sarapp_desktop_dir = repo_root / "apps" / "desktop" / "sarapp_desktop"
    sarapp_desktop_dir_str = str(sarapp_desktop_dir)
    if sarapp_desktop_dir.exists() and sarapp_desktop_dir_str not in sys.path:
        sys.path.insert(0, sarapp_desktop_dir_str)


_ensure_repo_packages_on_path()

from core.networking.server_info import DEFAULT_LOCAL_SERVER_NAME, DEFAULT_SERVER_PORT
from services.lan_server.server_manager import SARAppServerManager

DEFAULT_SERVER_HOST = "0.0.0.0"


def main() -> None:
    parser = argparse.ArgumentParser(description="Start a local SARApp incident server")
    parser.add_argument("--host", default=DEFAULT_SERVER_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_SERVER_PORT)
    parser.add_argument("--name", default=DEFAULT_LOCAL_SERVER_NAME)
    args = parser.parse_args()

    manager = SARAppServerManager(host=args.host, port=args.port, server_name=args.name)
    manager.start()
    print(f"SARApp Server running at http://{args.host}:{manager.port}")

    stop_event = threading.Event()

    def _handle_signal(sig, frame):
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    try:
        signal.signal(signal.SIGTERM, _handle_signal)
    except (OSError, ValueError):
        pass  # SIGTERM not supported on Windows

    stop_event.wait()
    manager.stop()


if __name__ == "__main__":
    main()
