"""Command-line entry point for the built-in SARApp incident server."""

from __future__ import annotations

import argparse

from core.networking.server_info import DEFAULT_LOCAL_SERVER_NAME, DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT
from server.server_manager import SARAppServerManager


def main() -> None:
    parser = argparse.ArgumentParser(description="Start a local SARApp incident server")
    parser.add_argument("--host", default=DEFAULT_SERVER_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_SERVER_PORT)
    parser.add_argument("--name", default=DEFAULT_LOCAL_SERVER_NAME)
    args = parser.parse_args()

    manager = SARAppServerManager(host=args.host, port=args.port, name=args.name)
    try:
        manager.serve_forever()
    except KeyboardInterrupt:
        manager.shutdown()


if __name__ == "__main__":
    main()
