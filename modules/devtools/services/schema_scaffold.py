from __future__ import annotations

from pathlib import Path
from typing import Optional
import json


SCHEMAS_DIR = Path("modules/forms/schemas")

KNOWN = {
    "ICS_205": "ics_205.schema.json",
    "ICS_204": "ics_204.schema.json",
    "ICS_214": "ics_214.schema.json",
    "ICS_203": "ics_203.schema.json",
    "ICS_206": "ics_206.schema.json",
}


def ensure_schema_for_form(form_id: str) -> Path:
    """Return a path to a schema for ``form_id``; create a skeleton if missing.

    For known base ICS forms, reuses a checked-in schema file. For unknown
    forms, generates a minimal skeleton with common buckets to enable guided
    binding suggestions that you can expand later.
    """

    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
    fid = (form_id or "").strip().upper()
    name = KNOWN.get(fid) or f"{fid.lower()}.schema.json"
    out = SCHEMAS_DIR / name
    if out.exists():
        return out

    # minimal skeleton shared by many ICS forms
    skeleton = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": f"{fid} Auto Skeleton",
        "type": "object",
        "properties": {
            "incident": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "number": {"type": "string"}}
            },
            "operational_period": {
                "type": "object",
                "properties": {"label": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"}}
            },
            "message": {
                "type": "object",
                "properties": {"to": {"type": "string"}, "from": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}}
            },
            "resources": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}}}},
            "communications": {"type": "object", "properties": {"channels": {"type": "array", "items": {"type": "object"}}}},
            "activity_log": {"type": "object", "properties": {"entries": {"type": "array", "items": {"type": "object"}}}},
        },
    }
    out.write_text(json.dumps(skeleton, indent=2), encoding="utf-8")
    return out


__all__ = ["ensure_schema_for_form", "SCHEMAS_DIR"]

