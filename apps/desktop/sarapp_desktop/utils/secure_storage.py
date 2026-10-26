"""Local, OS-tied secret storage for small values such as a remembered password.

Uses Windows DPAPI (``CryptProtectData``/``CryptUnprotectData``) so the
encrypted blob can only be decrypted by the same Windows user account on the
same machine - useless to anyone else even if ``settings.json`` (where the
blob is stored, base64-encoded, alongside the app's other settings) leaks or
is accidentally committed.
"""
from __future__ import annotations

import base64
import ctypes
import logging
import os
from ctypes import wintypes

logger = logging.getLogger(__name__)

try:
    import win32crypt
except ImportError:
    win32crypt = None


_DPAPI_AVAILABLE = win32crypt is not None or os.name == "nt"


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob_from_bytes(value: bytes) -> tuple[_DataBlob, ctypes.Array]:
    buffer = ctypes.create_string_buffer(value)
    blob = _DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    return blob, buffer


def _protect_with_ctypes(value: bytes) -> bytes:
    source, source_buffer = _blob_from_bytes(value)
    protected = _DataBlob()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(source), None, None, None, None, 0, ctypes.byref(protected)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(protected.pbData, protected.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(protected.pbData)


def _unprotect_with_ctypes(value: bytes) -> bytes:
    source, source_buffer = _blob_from_bytes(value)
    decrypted = _DataBlob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(source), None, None, None, None, 0, ctypes.byref(decrypted)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(decrypted.pbData, decrypted.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(decrypted.pbData)


def dpapi_available() -> bool:
    return _DPAPI_AVAILABLE


def encrypt_secret(value: str) -> str | None:
    """Encrypt ``value`` for storage. Returns a base64 string, or None if
    DPAPI isn't available or encryption fails - callers should treat None
    as "don't persist this value"."""

    if not value or not _DPAPI_AVAILABLE:
        return None
    try:
        if win32crypt is not None:
            encrypted = win32crypt.CryptProtectData(
                value.encode("utf-8"), None, None, None, None, 0
            )
        else:
            encrypted = _protect_with_ctypes(value.encode("utf-8"))
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
        if win32crypt is not None:
            _, decrypted = win32crypt.CryptUnprotectData(raw, None, None, None, 0)
        else:
            decrypted = _unprotect_with_ctypes(raw)
        return decrypted.decode("utf-8")
    except Exception:
        logger.exception("Failed to decrypt secret with DPAPI")
        return None


__all__ = ["dpapi_available", "encrypt_secret", "decrypt_secret"]
