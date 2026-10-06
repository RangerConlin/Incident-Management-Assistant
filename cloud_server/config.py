"""Configuration helpers for the hosted SARApp cloud server."""

from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _int_env(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class CloudSettings:
    server_name: str
    server_id: str
    connect_code: str
    admin_username: str
    admin_password_hash: str
    session_secret: str
    backup_dir: str
    config_dir: str
    firebase_credentials_path: str
    request_log_limit: int


def _password_hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def load_settings() -> CloudSettings:
    connect_code = _env("SARAPP_CONNECT_CODE", "CLOUD-0001").upper()
    password_hash = _env("CLOUD_ADMIN_PASSWORD_SHA256")
    if not password_hash:
        password_hash = _password_hash(_env("CLOUD_ADMIN_PASSWORD", "change-me"))
    return CloudSettings(
        server_name=_env("SARAPP_SERVER_NAME", f"SARApp Cloud Server DB {connect_code}"),
        server_id=_env("SARAPP_SERVER_ID", f"sarapp-cloud-server-db-{connect_code.lower()}"),
        connect_code=connect_code,
        admin_username=_env("CLOUD_ADMIN_USERNAME", "admin"),
        admin_password_hash=password_hash,
        session_secret=_env("CLOUD_SESSION_SECRET", secrets.token_urlsafe(32)),
        backup_dir=_env("CLOUD_BACKUP_DIR", "/var/lib/sarapp/backups"),
        config_dir=_env("CLOUD_CONFIG_DIR", "/var/lib/sarapp/config"),
        firebase_credentials_path=_env(
            "SARAPP_FIREBASE_CREDENTIALS_PATH",
            "/var/lib/sarapp/config/firebase_credentials.json",
        ),
        request_log_limit=_int_env("CLOUD_REQUEST_LOG_LIMIT", 500),
    )


def hash_password(password: str) -> str:
    return _password_hash(password)

