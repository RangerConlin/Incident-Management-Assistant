"""Source-checkout compatibility shim for the server-side ``sarapp_db`` package.

The real package lives under ``server/sarapp_db/sarapp_db``. Keeping this
shim lets existing in-repo imports continue to work when running tools from
the repository root without an editable install.
"""

from __future__ import annotations

from pathlib import Path

__path__ = [str(Path(__file__).resolve().parents[1] / "server" / "sarapp_db" / "sarapp_db")]
