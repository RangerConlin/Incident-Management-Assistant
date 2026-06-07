"""Dataclasses used by the Public Information module."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(slots=True)
class PIOMessage:
    id: Optional[int] = None
    title: str = ""
    subtitle: str = ""
    type: str = "Press Release"
    audience: str = "Public"
    priority: str = "Normal"
    status: str = "Draft"
    dateline: str = ""
    body: str = ""
    quote_block: str = ""
    safety_instructions: str = ""
    next_update_statement: str = ""
    created_by: str = ""
    approved_by: str = ""
    created_at: str = ""
    updated_at: str = ""
    published_at: str = ""
    related_incident_id: str = ""
    related_operational_period_id: str = ""
    template_id: Optional[int] = None


@dataclass(slots=True)
class PIOTemplate:
    id: Optional[int] = None
    template_name: str = ""
    template_type: str = "Press Release"
    agency_name: str = ""
    header_text: str = ""
    footer_text: str = ""
    contact_block: str = ""
    logo_path: str = ""
    release_label: str = ""
    default_classification_label: str = ""
    default_font_name: str = ""
    default_footer_disclaimer: str = ""
    is_active: int = 1
    created_at: str = ""
    updated_at: str = ""
    version: int = 1
