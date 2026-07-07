"""Entry point for the SARApp cloud router.

Runs as a headless service. No GUI. Intended to be started by a process
manager (systemd, Docker, etc.) or directly from the command line.

This process is a stateless reverse-tunnel proxy: it has no MongoDB
connection of its own. LAN servers dial out to it and register under a
connect code; field/remote devices hit `/r/<connect_code>/...` and their
requests are forwarded down the matching tunnel. See
`Design Documents/Instructions/cloud_router_architecture.md`.

Environment variables:
    SARAPP_CLOUD_ROUTER_TOKEN   Shared secret LAN servers must present to register a tunnel

Usage:
    python main.py
    python main.py --host 0.0.0.0 --port 8765 --name "Production Cloud Router"
"""

from __future__ import annotations

import argparse
import logging
import threading

from server_manager import SARAppServerManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("sarapp.cloud")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SARApp Cloud Router")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--name", default=None)
    args = parser.parse_args(argv)

    manager = SARAppServerManager(
        host=args.host,
        port=args.port,
        server_name=args.name,
    )
    manager.start()
    logger.info(
        "SARApp Cloud Router started — %s  port %d",
        manager.server_info.server_name,
        manager.port,
    )

    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        manager.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
