"""
SARApp database manager.

Provides helpers for obtaining the three logical MongoDB databases every
LAN/cloud server owns:
    - sarapp_system              (server configuration and state)
    - sarapp_master              (agency-wide reference data, local to this server)
    - sarapp_incident_<id>       (per-incident operational data)

A fourth database, sarapp_central_master, exists only inside cloud_router's
own embedded Mongo instance (see Design Documents/Instructions/
cloud_router_architecture.md). It holds the authoritative, centralized
agency-wide catalog that each server's local sarapp_master syncs with. It is
schema-identical to sarapp_master but deliberately named differently so a
misconfigured SARAPP_MONGO_URI can never cause a server to mistake its own
local master DB for the central one, or vice versa.

Used by the SARApp server runtime only. The desktop UI never calls this directly.
"""

from __future__ import annotations

import logging
import os
import re
from typing import TYPE_CHECKING

from pymongo.database import Database

from sarapp_db.mongo.mongo_client import get_client  # re-exported for routers
from sarapp_db.mongo.errors import DatabaseConnectionError, InvalidIncidentIdError

logger = logging.getLogger(__name__)

DB_SYSTEM = "sarapp_system"
DB_MASTER = "sarapp_master"
DB_INCIDENT_PREFIX = "sarapp_incident_"
DB_CENTRAL_MASTER = "sarapp_central_master"

# cloud_router sets this to DB_CENTRAL_MASTER before calling create_app(mode=
# "master_only") so the existing master routers (personnel.py, equipment.py,
# etc.) write to sarapp_central_master instead of sarapp_master, with zero
# changes to router code. Every LAN/cloud server leaves this unset and keeps
# using sarapp_master as always.
_MASTER_DB_NAME_ENV_VAR = "SARAPP_MASTER_DB_NAME"

# Only allow alphanumeric characters, hyphens, and underscores in incident IDs.
_SAFE_INCIDENT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")


def validate_incident_id(incident_id: str) -> None:
    """
    Validate that incident_id is safe to use as part of a MongoDB database name.

    Raises InvalidIncidentIdError for empty strings or unsafe characters.
    """
    if not incident_id or not incident_id.strip():
        raise InvalidIncidentIdError("incident_id must not be empty.")
    if not _SAFE_INCIDENT_ID_PATTERN.match(incident_id):
        raise InvalidIncidentIdError(
            f"incident_id '{incident_id}' contains unsafe characters. "
            "Only letters, numbers, hyphens, and underscores are allowed."
        )


def get_incident_db_name(incident_id: str) -> str:
    """Return the MongoDB database name for a given incident_id."""
    validate_incident_id(incident_id)
    return f"{DB_INCIDENT_PREFIX}{incident_id}"


def get_system_db() -> Database:
    """Return the sarapp_system database handle from the shared Mongo client."""
    return get_client()[DB_SYSTEM]


def _master_db_name() -> str:
    return os.environ.get(_MASTER_DB_NAME_ENV_VAR, "").strip() or DB_MASTER


def get_master_db() -> Database:
    """Return the master-catalog database handle from the shared Mongo client.

    Normally sarapp_master. Inside cloud_router's "master_only" process this
    resolves to sarapp_central_master instead (see _MASTER_DB_NAME_ENV_VAR),
    so the same master routers serve the central catalog unmodified.
    """
    return get_client()[_master_db_name()]


def get_central_master_db() -> Database:
    """Return the sarapp_central_master database handle directly.

    Only meaningful inside cloud_router's process, where SARAPP_MONGO_URI
    points at cloud_router's own embedded Mongo instance rather than a LAN
    or cloud server's local database.
    """
    return get_client()[DB_CENTRAL_MASTER]


def get_incident_db(incident_id: str) -> Database:
    """Return the per-incident database handle after validating incident_id."""
    return get_client()[get_incident_db_name(incident_id)]


class DatabaseManager:
    """
    Central access point for SARApp's MongoDB databases.

    Instantiate once per server process and pass it to services that need
    database access.
    """

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = get_client()
        return self._client

    def is_connected(self) -> bool:
        """Return True if MongoDB responds to a ping."""
        try:
            self._get_client().admin.command("ping")
            return True
        except Exception:
            return False

    def get_system_db(self) -> Database:
        """Return the sarapp_system database handle."""
        return self._get_client()[DB_SYSTEM]

    def get_master_db(self) -> Database:
        """Return the master-catalog database handle (sarapp_master, or
        sarapp_central_master inside cloud_router's master_only process)."""
        return self._get_client()[_master_db_name()]

    def get_central_master_db(self) -> Database:
        """Return the sarapp_central_master database handle (cloud_router only)."""
        return self._get_client()[DB_CENTRAL_MASTER]

    def get_incident_db(self, incident_id: str) -> Database:
        """
        Return the database handle for a specific incident.

        Raises InvalidIncidentIdError if the ID contains unsafe characters.
        """
        db_name = get_incident_db_name(incident_id)
        return self._get_client()[db_name]

    def create_indexes(self, incident_id: str) -> None:
        """
        Create all required indexes for the given incident database.

        Idempotent — safe to call on every server startup.
        """
        from sarapp_db.mongo.indexes import create_incident_indexes, create_master_indexes

        create_incident_indexes(self.get_incident_db(incident_id))
        create_master_indexes(self.get_master_db())
        logger.info("Indexes created/verified for incident '%s'.", incident_id)
