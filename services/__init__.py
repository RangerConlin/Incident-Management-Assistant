"""Service packages.

This package is intentionally namespace-extended during the staged repo
reorganization: LAN/cloud service packages live at repository root while
desktop-only service helpers can be exposed from apps/desktop/sarapp_desktop
when that directory is on sys.path.
"""

from __future__ import annotations

from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)
