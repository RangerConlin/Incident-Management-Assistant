"""Command-line entry point for starting a local SARApp incident server."""

from __future__ import annotations

import argparse
from pathlib import Path
import signal
import sys


def _ensure_repo_packages_on_path() -> None:
    """Allow local runs without requiring editable installs first."""
    repo_root = Path(__file__).resolve().parent
    package_roots = (
        repo_root / "cloud_server",
        repo_root / "data" / "db",
    )
    for package_root in package_roots:
        package_root_str = str(package_root)
        if package_root.exists() and package_root_str not in sys.path:
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
