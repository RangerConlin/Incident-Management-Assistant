"""
Firebase Admin SDK client wrapper for FCM push notifications.

URI resolution order mirrors sarapp_db.mongo.mongo_client:
    1. SARAPP_FIREBASE_CREDENTIALS_PATH environment variable
    2. no fallback — raises FirebaseNotConfiguredError

Credentials are never baked in; the service-account JSON path is read from
the environment only.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import firebase_admin
from firebase_admin import credentials

logger = logging.getLogger(__name__)

_CREDENTIALS_PATH_ENV_VAR = "SARAPP_FIREBASE_CREDENTIALS_PATH"

_app: Optional[firebase_admin.App] = None


class FirebaseNotConfiguredError(RuntimeError):
    """Raised when SARAPP_FIREBASE_CREDENTIALS_PATH is unset or invalid."""


def get_firebase_app() -> firebase_admin.App:
    """
    Return the shared Firebase Admin App for this server process.

    Creates the app on first call and reuses it thereafter.
    Raises FirebaseNotConfiguredError if the credentials env var is unset
    or points at a missing file.
    """
    global _app
    if _app is not None:
        return _app

    cred_path = os.environ.get(_CREDENTIALS_PATH_ENV_VAR, "").strip()
    if not cred_path:
        raise FirebaseNotConfiguredError(
            f"{_CREDENTIALS_PATH_ENV_VAR} is not set; cannot initialize Firebase Admin SDK."
        )
    if not os.path.isfile(cred_path):
        raise FirebaseNotConfiguredError(f"Firebase credential file not found: {cred_path}")

    cred = credentials.Certificate(cred_path)
    _app = firebase_admin.initialize_app(cred)
    logger.info("Firebase Admin SDK initialized.")
    return _app
