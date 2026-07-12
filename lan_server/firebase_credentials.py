"""Resolves which Firebase Admin SDK credentials file the LAN server uses.

Two sources, in priority order:
    1. An end user's uploaded key (persisted via ServerConsoleSettings.firebase_credentials_path,
       stored at settings/firebase_credentials.json so it survives restarts without re-upload).
    2. A bundled default key JSON committed directly in this folder (matched by
       Firebase's standard "*-firebase-adminsdk-*.json" naming convention).

Either way, the resolved path is exposed to the rest of the app the same way
every other secret already is: via SARAPP_FIREBASE_CREDENTIALS_PATH in the
environment, read by sarapp_db.services.firebase_client.get_firebase_app().
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lan_server.server_console.settings import ServerConsoleSettings

_ENV_VAR = "SARAPP_FIREBASE_CREDENTIALS_PATH"
_BUNDLED_DEFAULT_GLOB = "*firebase-adminsdk*.json"
_UPLOADED_KEY_FILENAME = "firebase_credentials.json"


def lan_server_dir() -> Path:
    return Path(__file__).resolve().parent


def uploaded_key_path() -> Path:
    """Stable destination for an end user's uploaded key, inside settings/."""
    return lan_server_dir() / "settings" / _UPLOADED_KEY_FILENAME


def find_bundled_default() -> Path | None:
    """Return the bundled default credentials file shipped in this folder, if any.

    If more than one match exists (shouldn't happen in normal use), the most
    recently modified one wins rather than raising, since server startup
    must never be blocked by an ambiguous-but-recoverable state.
    """
    matches = sorted(
        lan_server_dir().glob(_BUNDLED_DEFAULT_GLOB),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else None


def resolve_credentials_path(settings: "ServerConsoleSettings") -> Path | None:
    """Return the credentials file to use: an explicit upload, else the bundled default."""
    configured = (settings.firebase_credentials_path or "").strip()
    if configured:
        path = Path(configured)
        if path.is_file():
            return path
    return find_bundled_default()


def apply_credentials_env(settings: "ServerConsoleSettings") -> Path | None:
    """Set SARAPP_FIREBASE_CREDENTIALS_PATH from the resolved source, if any.

    Called once at server start. Intentionally does not clear the env var
    when nothing resolves — get_firebase_app() already raises a clear
    FirebaseNotConfiguredError on first use in that case.
    """
    resolved = resolve_credentials_path(settings)
    if resolved is not None:
        os.environ[_ENV_VAR] = str(resolved)
    return resolved


def store_uploaded_credentials(source: Path) -> Path:
    """Copy an end user's selected key into the persisted upload slot.

    Returns the stable destination path to save into
    ServerConsoleSettings.firebase_credentials_path.
    """
    destination = uploaded_key_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return destination
