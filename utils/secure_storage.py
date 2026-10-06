"""Local, OS-tied secret storage for small values such as a remembered password.

Uses Windows DPAPI (``CryptProtectData``/``CryptUnprotectData``) so the
encrypted blob can only be decrypted by the same Windows user account on the
same machine - useless to anyone else even if ``settings.json`` (where the
blob is stored, base64-encoded, alongside the app's other settings) leaks or
is accidentally committed.
"""
from __future__ import annotations

import base64
import logging

logger = logging.getLogger(__name__)

try:
    import win32crypt

    _DPAPI_AVAILABLE = True
except ImportError:
    _DPAPI_AVAILABLE = False


def dpapi_available() -> bool:
    return _DPAPI_AVAILABLE


def encrypt_secret(value: str) -> str | None:
    """Encrypt ``value`` for storage. Returns a base64 string, or None if
    DPAPI isn't available or encryption fails - callers should treat None
    as "don't persist this value"."""

    if not value or not _DPAPI_AVAILABLE:
        return None
    try:
        encrypted = win32crypt.CryptProtectData(value.encode("utf-8"), None, None, None, None, 0)
        return base64.b64encode(encrypted).decode("ascii")
    except Exception:
        logger.exception("Failed to encrypt secret with DPAPI")
        return None


def decrypt_secret(encoded: str) -> str | None:
    """Decrypt a value produced by ``encrypt_secret``. Returns None on
    failure (e.g. DPAPI unavailable, blob from a different Windows account,
    or corrupted data) - callers should treat None as "nothing remembered"."""

    if not encoded or not _DPAPI_AVAILABLE:
        return None
    try:
        raw = base64.b64decode(encoded)
        _, decrypted = win32crypt.CryptUnprotectData(raw, None, None, None, 0)
        return decrypted.decode("utf-8")
    except Exception:
        logger.exception("Failed to decrypt secret with DPAPI")
        return None


__all__ = ["dpapi_available", "encrypt_secret", "decrypt_secret"]
