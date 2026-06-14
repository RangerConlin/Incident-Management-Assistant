"""Shim — intel module now uses the SARApp API (MongoDB).

Functions here are kept for import compatibility but do nothing;
panels use modules.intel.services directly.
"""

from __future__ import annotations


def ensure_incident_schema() -> None:
    pass
