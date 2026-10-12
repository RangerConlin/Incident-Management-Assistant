"""Shared TLS configuration for SARApp network clients."""

from __future__ import annotations

import ssl
from functools import lru_cache


@lru_cache(maxsize=1)
def system_ssl_context() -> ssl.SSLContext:
    """Return a verified TLS context backed by the operating-system roots.

    SARApp is desktop-first, so HTTPS/WSS clients must honor certificates
    installed in the Windows trust store, including enterprise and antivirus
    inspection roots.  ``ssl.create_default_context`` keeps normal chain and
    hostname verification enabled while loading those platform roots.
    """

    return ssl.create_default_context()
