"""
Custom exceptions for the SARApp MongoDB database framework.

These exceptions are raised by server-side database code only.
The desktop UI should never catch these directly — it communicates
through the SARApp server API layer.
"""


class DatabaseConnectionError(Exception):
    """Raised when the MongoDB server cannot be reached or authenticated."""


class DatabaseConfigurationError(Exception):
    """Raised for missing or invalid database configuration (e.g. bad URI format)."""


class InvalidIncidentIdError(ValueError):
    """
    Raised when an incident_id contains characters that are unsafe for use in
    a MongoDB database name (spaces, path separators, special punctuation, or empty string).
    """


class RepositoryError(Exception):
    """Raised for unexpected failures in repository read/write operations."""


class AuditWriteError(Exception):
    """Raised when an audit log record cannot be written to the database."""
