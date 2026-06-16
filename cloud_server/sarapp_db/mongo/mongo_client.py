"""
SARApp MongoDB client wrapper.

This module is used by the SARApp server runtime (LAN, cloud, or local offline).
The desktop UI does not import this module — it communicates with the server via API.

URI resolution order:
    1. SARAPP_MONGO_URI environment variable  (set in production/staging server config)
    2. mongodb://localhost:27017              (default for local dev and offline mode)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError

from sarapp_db.mongo.errors import DatabaseConnectionError, DatabaseConfigurationError

logger = logging.getLogger(__name__)

_URI_ENV_VAR = "SARAPP_MONGO_URI"
_DEFAULT_URI = "mongodb://localhost:27017"

_client: Optional[MongoClient] = None


def get_mongo_uri() -> str:
    """
    Return the MongoDB URI for this server instance.

    Reads SARAPP_MONGO_URI from the environment. Falls back to localhost
    for local development and offline mode. No credentials are ever baked in.
    """
    uri = os.environ.get(_URI_ENV_VAR, "").strip()
    if uri:
        logger.debug("Using MongoDB URI from %s", _URI_ENV_VAR)
        return uri
    logger.debug("%s not set — defaulting to %s", _URI_ENV_VAR, _DEFAULT_URI)
    return _DEFAULT_URI


def get_client() -> MongoClient:
    """
    Return the shared MongoClient for this server process.

    Creates the client on first call and reuses it thereafter.
    Raises DatabaseConnectionError if the server is unreachable.
    Raises DatabaseConfigurationError if the URI is malformed.
    """
    global _client
    if _client is not None:
        return _client

    uri = get_mongo_uri()
    try:
        client: MongoClient = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        _client = client
        logger.info("MongoDB client connected.")
        return _client
    except ConnectionFailure as exc:
        raise DatabaseConnectionError(
            f"Cannot connect to MongoDB at '{uri}': {exc}"
        ) from exc
    except ConfigurationError as exc:
        raise DatabaseConfigurationError(
            f"MongoDB URI configuration error: {exc}"
        ) from exc


def close_client() -> None:
    """Close the shared MongoClient. Call during server shutdown."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("MongoDB client closed.")


def ping() -> bool:
    """Return True if the MongoDB server responds to a ping, False otherwise."""
    try:
        get_client().admin.command("ping")
        return True
    except Exception:
        return False
