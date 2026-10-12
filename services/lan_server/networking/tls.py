"""TLS configuration for SARApp LAN/cloud network clients."""

from __future__ import annotations

import ssl
from functools import lru_cache


@lru_cache(maxsize=1)
def system_ssl_context() -> ssl.SSLContext:
    """Return a verified TLS context backed by operating-system roots."""

    return ssl.create_default_context()
