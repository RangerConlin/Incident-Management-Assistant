"""Very small placeholder rules DSL used for event ingestion."""
from __future__ import annotations

from typing import Dict, Any


def render_template(template: str, payload: Dict[str, Any]) -> str:
    """Format *template* using payload as variables."""
    try:
        return template.format(**payload)
    except Exception:
        return template
