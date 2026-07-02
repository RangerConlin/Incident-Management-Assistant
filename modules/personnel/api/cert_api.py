"""Personnel certification API for UI usage.

This API reads the catalog from the MongoDB master DB and edits embedded
personnel certification levels. A personnel cert stores only cert_type_id and
level; display data comes from the catalog.
"""

from __future__ import annotations

from typing import List, Dict, Any

from utils.api_client import api_client
from utils.app_settings import DEV_MODE
from modules.personnel.models.cert_catalog import CATALOG
from modules.personnel.models.validation_profiles import PROFILES, get_profile


def list_catalog(filter_text: str = "", category: str | None = None) -> List[Dict[str, Any]]:
    """Return certification types from the hardcoded catalog."""
    results = [
        {
            "id": ct.id,
            "int_id": ct.id,
            "code": ct.code,
            "name": ct.name,
            "category": ct.category,
            "issuing_org": ct.issuing_org,
            "parent_id": ct.parent_id,
            "tags": list(ct.tags),
            "is_medical": ct.is_medical,
        }
        for ct in CATALOG
    ]
    if category:
        results = [c for c in results if c["category"] == category]
    if filter_text:
        ft = filter_text.lower()
        results = [
            c for c in results
            if ft in c["code"].lower() or ft in c["name"].lower()
            or ft in c["category"].lower() or ft in c["issuing_org"].lower()
        ]
    return sorted(results, key=lambda c: (c["category"], c["code"]))


def list_tags_for_cert(cert_type_id: int) -> list[str]:
    for ct in CATALOG:
        if ct.id == cert_type_id:
            return list(ct.tags)
    return []


def list_personnel_certs(personnel_id: int) -> List[Dict[str, Any]]:
    """Return a person's certifications enriched with catalog display data."""
    try:
        rows = api_client.get(f"/api/master/certifications/personnel/{personnel_id}") or []
    except Exception:
        return []
    catalog_by_id = {ct.id: ct for ct in CATALOG}
    result = []
    for row in rows:
        try:
            cert_type_id = int(row["cert_type_id"])
        except (KeyError, TypeError, ValueError):
            continue
        ct = catalog_by_id.get(cert_type_id)
        result.append({
            "cert_type_id": cert_type_id,
            "id": cert_type_id,
            "level": int(row.get("level") or 0),
            "code": ct.code if ct else "",
            "name": ct.name if ct else "",
            "category": ct.category if ct else "",
            "issuing_org": ct.issuing_org if ct else "",
            "parent_id": ct.parent_id if ct else None,
            "tags": list(ct.tags) if ct else [],
            "is_medical": ct.is_medical if ct else False,
        })
    return sorted(result, key=lambda c: (c["category"], c["code"]))


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
