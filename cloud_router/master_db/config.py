"""Settings for the central master-catalog web GUI.

Same env-var-driven, session-cookie auth pattern as
``cloud_server/config.py`` + ``cloud_server/dashboard.py``. The env admin
account is the bootstrap login; additional simple console users are managed
inside the central master GUI.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _password_hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    return _password_hash(password)


@dataclass(frozen=True)
class MasterGuiSettings:
    admin_username: str
    admin_password_hash: str
    session_secret: str


def load_settings() -> MasterGuiSettings:
    password_hash = _env("CENTRAL_MASTER_ADMIN_PASSWORD_SHA256")
    if not password_hash:
        password_hash = _password_hash(_env("CENTRAL_MASTER_ADMIN_PASSWORD", "change-me"))
    return MasterGuiSettings(
        admin_username=_env("CENTRAL_MASTER_ADMIN_USERNAME", "admin"),
        admin_password_hash=password_hash,
        session_secret=_env("CENTRAL_MASTER_SESSION_SECRET", secrets.token_urlsafe(32)),
    )
