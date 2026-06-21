"""Entry point for the SARApp cloud server.

Runs as a headless service. No GUI. Intended to be started by a process
manager (systemd, Docker, etc.) or directly from the command line.

Environment variables:
    SARAPP_MONGO_URI    MongoDB connection URI (required in production)

Usage:
    python main.py
    python main.py --host 0.0.0.0 --port 8765 --name "Production Cloud Server"
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading

from server_manager import SARAppServerManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("sarapp.cloud")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SARApp Cloud Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--name", default=None)
    parser.add_argument(
        "--discovery",
        action="store_true",
        default=False,
        help="Enable LAN UDP discovery broadcasting (off by default on cloud)",
    )
    args = parser.parse_args(argv)

    manager = SARAppServerManager(
        host=args.host,
        port=args.port,
        server_name=args.name,
        discovery_enabled=args.discovery,
    )
    manager.start()
    logger.info(
        "SARApp Cloud Server started — %s  port %d",
        manager.server_info.server_name,
        manager.port,
    )

    # TODO: wire in DatabaseManager and API routes here when ready
    # from sarapp_db.mongo.database_manager import DatabaseManager
    # db = DatabaseManager()
    # if not db.is_connected():
    #     logger.error("MongoDB unavailable — check SARAPP_MONGO_URI")
    #     manager.stop()
    #     return 1

    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        manager.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
