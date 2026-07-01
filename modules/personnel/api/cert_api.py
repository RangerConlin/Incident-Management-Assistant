"""Personnel certification API for UI usage.

This API reads the catalog from the MongoDB master DB and edits embedded
personnel certification levels. A personnel cert stores only cert_type_id and
level; display data comes from the catalog.
"""

from __future__ import annotations

from typing import List, Dict, Any

from utils.api_client import api_client
from utils.app_settings import DEV_MODE
from modules.personnel.models.validation_profiles import PROFILES, get_profile


def list_catalog(filter_text: str = "", category: str | None = None) -> List[Dict[str, Any]]:
    """List catalog types from the API with optional filters."""
    try:
        params = {}
        if filter_text:
            params["search"] = filter_text
        certs = api_client.get("/api/master/certifications/types", params=params) or []
        if category:
            certs = [c for c in certs if c.get("category") == category]
        return certs
    except Exception:
        return []


def list_tags_for_cert(cert_type_id: int) -> list[str]:
    try:
        return api_client.get(f"/api/master/certifications/types/{cert_type_id}/tags") or []
    except Exception:
        return []


def list_personnel_certs(personnel_id: int) -> List[Dict[str, Any]]:
    """Return the person's certifications from the API.

    The API returns catalog-enriched rows for UI display, but the stored
    personnel document only contains cert_type_id and level.
    """
    try:
        return api_client.get(f"/api/master/certifications/personnel/{personnel_id}") or []
    except Exception:
        return []


def set_personnel_cert(
    personnel_id: int,
    cert_type_id: int,
    level: int,
    attachment_url: str | None = None,
) -> None:
    """Insert or update a person's certification level via API.

    attachment_url is accepted for backward compatibility with older callers but
    is intentionally not sent or stored.
    """
    try:
        lvl = max(0, min(3, int(level)))
        api_client.post(
            f"/api/master/certifications/personnel/{personnel_id}/{cert_type_id}",
            json={"level": lvl},
        )
    except Exception:
        pass


def delete_personnel_cert(personnel_id: int, cert_type_id: int) -> None:
    try:
        api_client.delete(f"/api/master/certifications/personnel/{personnel_id}/{cert_type_id}")
    except Exception:
        pass


def list_profiles() -> list[dict]:
    return [
        {"code": p.code, "name": p.name, "min_level": p.min_level}
        for p in PROFILES
    ]


def person_meets_profile(personnel_id: int, profile_code: str) -> bool:
    """Determine if a person meets a given profile.

    Rules:
    - Consider the highest level per certification.
    - Require level >= profile.min_level.
    - Require cert has all_tags (if any) and at least one any_tag (if any).
    """
    prof = get_profile(profile_code)
    if prof is None:
        return False

    try:
        certs = list_personnel_certs(personnel_id)
    except Exception:
        certs = []

    max_levels: dict[int, int] = {}
    for c in certs:
        try:
            cid = int(c.get("cert_type_id"))
            lvl = int(c.get("level") or 0)
        except (TypeError, ValueError):
            continue
        max_levels[cid] = max(max_levels.get(cid, 0), lvl)

    for cert_type_id, lvl in max_levels.items():
        if lvl < prof.min_level:
            continue
        try:
            tags: set[str] = set(list_tags_for_cert(cert_type_id) or [])
        except Exception:
            tags = set()
        if prof.all_tags and not all(t in tags for t in prof.all_tags):
            continue
        if prof.any_tags and not any(t in tags for t in prof.any_tags):
            continue
        return True
    return False


def ensure_catalog_write_allowed() -> None:
    if not DEV_MODE:
        raise PermissionError("Catalog mutations are blocked in production build")


__all__ = [
    "list_catalog",
    "list_personnel_certs",
    "set_personnel_cert",
    "delete_personnel_cert",
    "list_tags_for_cert",
    "list_profiles",
    "person_meets_profile",
    "ensure_catalog_write_allowed",
]
