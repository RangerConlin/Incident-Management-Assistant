"""Shared, Qt-free personnel master-catalog field list + import/export row
mapping. Used by both the desktop Edit-menu window (`ui/personnel/
ui_personnel.py`) and the central web GUI (`cloud_router/master_db/
webgui.py`), so an exported file from one is importable into the other —
same columns, same row-level transformation (name fallback, emergency/
contact grouping, certification code parsing).

Deliberately has no PySide6 import anywhere in this module (unlike
`utils/edit_window_kit.py`, which this would otherwise need to import
`FieldSpec` from) — the central web GUI runs inside cloud_router's process,
which has no Qt dependency and shouldn't gain one just to reuse this.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class FieldSpec:
    key: str
    label: str
    required: bool = False
    in_export_default: bool = True


def clean_text(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


def bool_from_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    return text in {"1", "true", "t", "yes", "y", "on"}


def _clamp_level(value: Any) -> int:
    try:
        return max(0, min(3, int(value)))
    except (TypeError, ValueError):
        return 0


def certification_catalogs() -> tuple[dict[str, int], dict[int, dict[str, Any]]]:
    """Return (catalog_by_code, catalog_by_id) from the master certification
    type catalog. Calls the router function directly rather than through
    HTTP — every caller of this (cloud_router's web GUI, the catalog export
    script) already runs in the same process as the master Mongo
    connection, same as how webgui.py calls every other master router
    directly rather than looping back through its own API."""
    from sarapp_db.api.routers.certification_types import list_certification_types

    by_code: dict[str, int] = {}
    by_id: dict[int, dict[str, Any]] = {}
    # Called as a plain Python function, not through FastAPI's request
    # pipeline — every parameter must be passed explicitly, or the ones
    # whose real default is a fastapi.params.Query sentinel (not a plain
    # Python value) get used as-is and blow up downstream (see the same
    # caution in cloud_router/master_db/webgui.py).
    for row in list_certification_types(search="", category="", include_inactive=True):
        by_id[row["id"]] = {"code": row.get("code", ""), "name": row.get("name", "")}
        code = row.get("code")
        if code:
            by_code[str(code).strip().upper()] = row["id"]
    return by_code, by_id


def format_certifications(certs: Any, catalog_by_id: Optional[dict[int, dict[str, Any]]] = None) -> str:
    if not certs:
        return ""
    catalog_by_id = catalog_by_id or {}
    parts: list[str] = []
    for cert in certs:
        if not isinstance(cert, dict):
            continue
        cert_type_id = cert.get("cert_type_id") or cert.get("id") or cert.get("certification_type_id")
        if cert_type_id in (None, ""):
            continue
        try:
            cert_type_id_int = int(cert_type_id)
        except (TypeError, ValueError):
            continue
        catalog_row = catalog_by_id.get(cert_type_id_int) or {}
        code = clean_text(catalog_row.get("code")) or str(cert_type_id_int)
        level = _clamp_level(cert.get("level"))
        parts.append(f"{code}:{level}")
    return "; ".join(parts)


def parse_certifications(value: Any, catalog_by_code: Optional[dict[str, int]] = None) -> list[dict[str, int]]:
    catalog_by_code = {k.upper(): v for k, v in (catalog_by_code or {}).items()}
    if not value:
        return []

    raw_items: list[Any]
    if isinstance(value, list):
        raw_items = list(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = None
            else:
                if isinstance(parsed, list):
                    return parse_certifications(parsed, catalog_by_code)
        raw_items = [part.strip() for part in re.split(r"[;\n|]+", text) if part.strip()]
    else:
        raw_items = [value]

    rows: dict[int, dict[str, int]] = {}
    for item in raw_items:
        cert_type_id: Any = None
        level = 0

        if isinstance(item, dict):
            raw_cert = item.get("cert_type_id") or item.get("id") or item.get("code")
            level = _clamp_level(item.get("level"))
        else:
            token = clean_text(item)
            if not token:
                continue
            if ":" in token:
                raw_cert, level_text = token.split(":", 1)
                level = _clamp_level(level_text)
            elif "=" in token:
                raw_cert, level_text = token.split("=", 1)
                level = _clamp_level(level_text)
            else:
                raw_cert = token
            raw_cert = clean_text(raw_cert)

        if isinstance(raw_cert, int):
            cert_type_id = raw_cert
        else:
            raw_text = clean_text(raw_cert)
            if raw_text.isdigit():
                cert_type_id = int(raw_text)
            else:
                cert_type_id = catalog_by_code.get(raw_text.upper())

        if cert_type_id is None:
            continue
        rows[cert_type_id] = {"cert_type_id": int(cert_type_id), "level": level}

    return sorted(rows.values(), key=lambda item: item["cert_type_id"])


def personnel_export_row(doc: dict[str, Any], catalog_by_id: Optional[dict[int, dict[str, Any]]] = None) -> dict[str, Any]:
    emergency = doc.get("emergency_info") or {}
    contact = doc.get("contact_info") or {}

    full_name = clean_text(doc.get("name") or doc.get("full_name"))
    first_name = clean_text(doc.get("first_name"))
    last_name = clean_text(doc.get("last_name"))
    if not first_name and not last_name and full_name:
        name_parts = full_name.split(None, 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

    is_medic = doc.get("is_medic")
    if is_medic is None:
        is_medic = doc.get("medic")

    certs = doc.get("certifications")
    if certs is None:
        certs = doc.get("certs")

    return {
        "person_id": clean_text(doc.get("person_id") or doc.get("personnel_id")),
        "name": full_name,
        "first_name": first_name,
        "last_name": last_name,
        "callsign": clean_text(doc.get("callsign")),
        "rank": clean_text(doc.get("rank")),
        "home_unit": clean_text(doc.get("home_unit")),
        "title": clean_text(doc.get("title")),
        "status": clean_text(doc.get("status")) or "available",
        "email": clean_text(doc.get("email")),
        "phone": clean_text(doc.get("phone")),
        "radio_id": clean_text(doc.get("radio_id")),
        "is_medic": "Yes" if bool_from_value(is_medic) else "No",
        "notes": clean_text(doc.get("notes")),
        "photo_url": clean_text(doc.get("photo_url")),
        "emergency_primary_name": clean_text(emergency.get("primary_name")),
        "emergency_primary_relationship": clean_text(emergency.get("primary_relationship")),
        "emergency_primary_phone": clean_text(emergency.get("primary_phone")),
        "emergency_secondary_name": clean_text(emergency.get("secondary_name")),
        "emergency_secondary_relationship": clean_text(emergency.get("secondary_relationship")),
        "emergency_secondary_phone": clean_text(emergency.get("secondary_phone")),
        "emergency_medical": clean_text(emergency.get("medical")),
        "emergency_blood_type": clean_text(emergency.get("blood_type")),
        "emergency_insurance": clean_text(emergency.get("insurance")),
        "contact_address1": clean_text(contact.get("address1")),
        "contact_address2": clean_text(contact.get("address2")),
        "contact_city": clean_text(contact.get("city")),
        "contact_state": clean_text(contact.get("state")),
        "contact_zip": clean_text(contact.get("zip")),
        "contact_work_phone": clean_text(contact.get("work_phone")),
        "contact_secondary_phone": clean_text(contact.get("secondary_phone")),
        "contact_pager_id": clean_text(contact.get("pager_id")),
        "contact_notes": clean_text(contact.get("notes")),
        "certifications": format_certifications(certs, catalog_by_id),
    }


def build_personnel_import_payload(row: dict[str, Any], catalog_by_code: Optional[dict[str, int]] = None) -> dict[str, Any]:
    catalog_by_code = catalog_by_code or {}
    name = clean_text(row.get("name"))
    first_name = clean_text(row.get("first_name"))
    last_name = clean_text(row.get("last_name"))
    if not name:
        name = " ".join(part for part in (first_name, last_name) if part).strip()
    if not name:
        raise ValueError("Name is required.")

    home_unit = clean_text(row.get("home_unit"))

    emergency = {
        "primary_name": clean_text(row.get("emergency_primary_name")),
        "primary_relationship": clean_text(row.get("emergency_primary_relationship")),
        "primary_phone": clean_text(row.get("emergency_primary_phone")),
        "secondary_name": clean_text(row.get("emergency_secondary_name")),
        "secondary_relationship": clean_text(row.get("emergency_secondary_relationship")),
        "secondary_phone": clean_text(row.get("emergency_secondary_phone")),
        "medical": clean_text(row.get("emergency_medical")),
        "blood_type": clean_text(row.get("emergency_blood_type")),
        "insurance": clean_text(row.get("emergency_insurance")),
    }
    emergency = {k: v for k, v in emergency.items() if v}

    contact = {
        "address1": clean_text(row.get("contact_address1")),
        "address2": clean_text(row.get("contact_address2")),
        "city": clean_text(row.get("contact_city")),
        "state": clean_text(row.get("contact_state")),
        "zip": clean_text(row.get("contact_zip")),
        "work_phone": clean_text(row.get("contact_work_phone")),
        "secondary_phone": clean_text(row.get("contact_secondary_phone")),
        "pager_id": clean_text(row.get("contact_pager_id")),
        "notes": clean_text(row.get("contact_notes")),
    }
    contact = {k: v for k, v in contact.items() if v}

    payload: dict[str, Any] = {
        "person_id": clean_text(row.get("person_id")),
        "name": name,
        "first_name": first_name,
        "last_name": last_name,
        "callsign": clean_text(row.get("callsign")),
        "rank": clean_text(row.get("rank")),
        "home_unit": home_unit,
        "title": clean_text(row.get("title")),
        "status": clean_text(row.get("status")) or "available",
        "email": clean_text(row.get("email")),
        "phone": clean_text(row.get("phone")),
        "radio_id": clean_text(row.get("radio_id")),
        "is_medic": bool_from_value(row.get("is_medic")),
        "notes": clean_text(row.get("notes")),
        "photo_url": clean_text(row.get("photo_url")),
        "certifications": parse_certifications(row.get("certifications"), catalog_by_code),
    }
    if emergency:
        payload["emergency_info"] = emergency
    if contact:
        payload["contact_info"] = contact
    return payload


PERSONNEL_FIELDS: list[FieldSpec] = [
    FieldSpec("person_id", "Personnel ID"),
    FieldSpec("name", "Name", required=True),
    FieldSpec("first_name", "First Name"),
    FieldSpec("last_name", "Last Name"),
    FieldSpec("callsign", "Callsign"),
    FieldSpec("rank", "Rank"),
    FieldSpec("home_unit", "Organization"),
    FieldSpec("title", "Title"),
    FieldSpec("status", "Status"),
    FieldSpec("email", "Email"),
    FieldSpec("phone", "Phone"),
    FieldSpec("radio_id", "Radio ID"),
    FieldSpec("is_medic", "Medic"),
    FieldSpec("notes", "Notes"),
    FieldSpec("photo_url", "Photo URL"),
    FieldSpec("emergency_primary_name", "Emergency Primary Name"),
    FieldSpec("emergency_primary_relationship", "Emergency Primary Relationship"),
    FieldSpec("emergency_primary_phone", "Emergency Primary Phone"),
    FieldSpec("emergency_secondary_name", "Emergency Secondary Name"),
    FieldSpec("emergency_secondary_relationship", "Emergency Secondary Relationship"),
    FieldSpec("emergency_secondary_phone", "Emergency Secondary Phone"),
    FieldSpec("emergency_medical", "Emergency Medical"),
    FieldSpec("emergency_blood_type", "Emergency Blood Type"),
    FieldSpec("emergency_insurance", "Emergency Insurance"),
    FieldSpec("contact_address1", "Contact Address 1"),
    FieldSpec("contact_address2", "Contact Address 2"),
    FieldSpec("contact_city", "Contact City"),
    FieldSpec("contact_state", "Contact State"),
    FieldSpec("contact_zip", "Contact ZIP"),
    FieldSpec("contact_work_phone", "Contact Work Phone"),
    FieldSpec("contact_secondary_phone", "Contact Secondary Phone"),
    FieldSpec("contact_pager_id", "Contact Pager / Radio ID"),
    FieldSpec("contact_notes", "Contact Notes"),
    FieldSpec("certifications", "Certifications"),
]
PERSONNEL_FIELD_LABELS = {spec.key: spec.label for spec in PERSONNEL_FIELDS}
