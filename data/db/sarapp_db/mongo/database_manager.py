"""
SARApp database manager.

Provides helpers for obtaining the three logical MongoDB databases:
    - sarapp_system              (server configuration and state)
    - sarapp_master              (agency-wide reference data)
    - sarapp_incident_<id>       (per-incident operational data)

Used by the SARApp server runtime only. The desktop UI never calls this directly.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from pymongo.database import Database

from sarapp_db.mongo.mongo_client import get_client
from sarapp_db.mongo.errors import DatabaseConnectionError, InvalidIncidentIdError

logger = logging.getLogger(__name__)

DB_SYSTEM = "sarapp_system"
DB_MASTER = "sarapp_master"
DB_INCIDENT_PREFIX = "sarapp_incident_"

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
        """Return the sarapp_master database handle."""
        return self._get_client()[DB_MASTER]

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
