"""Personnel certification API for UI usage.

This API reads the certification type catalog and edits embedded personnel
certification levels, both via the MongoDB-backed master API. A personnel
cert stores only cert_type_id and level; display data comes from the
catalog (`/api/master/certification-types`, see
data/db/sarapp_db/api/routers/certification_types.py — a central-catalog
-authoritative "lockdown" collection, same as organizations/resource types).
"""

from __future__ import annotations

from typing import List, Dict, Any

from utils.api_client import api_client

_CATALOG_BASE = "/api/master/certification-types"
_QUALIFICATIONS_BASE = "/api/master/qualification-types"


def list_catalog(filter_text: str = "", category: str | None = None) -> List[Dict[str, Any]]:
    """Return certification types from the master catalog."""
    try:
        params: dict[str, Any] = {}
        if filter_text:
            params["search"] = filter_text
        if category:
            params["category"] = category
        rows = api_client.get(_CATALOG_BASE, params=params) or []
    except Exception:
        return []
    results = [
        {
            "id": row["id"],
            "int_id": row["id"],
            "code": row.get("code", ""),
            "name": row.get("name", ""),
            "category": row.get("category", ""),
            "issuing_org": row.get("issuing_org", ""),
            "parent_id": row.get("parent_id"),
            "tags": list(row.get("tags") or []),
            "is_medical": bool(row.get("is_medical", False)),
        }
        for row in rows
    ]
    return sorted(results, key=lambda c: (c["category"], c["code"]))


def list_tags_for_cert(cert_type_id: int) -> list[str]:
    try:
        row = api_client.get(f"{_CATALOG_BASE}/{cert_type_id}")
    except Exception:
        return []
    return list((row or {}).get("tags") or [])


def list_personnel_certs(personnel_id: int) -> List[Dict[str, Any]]:
    """Return a person's certifications enriched with catalog display data."""
    try:
        rows = api_client.get(f"/api/master/certifications/personnel/{personnel_id}") or []
    except Exception:
        return []
    catalog_by_id = {ct["id"]: ct for ct in list_catalog()}
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
            "code": ct["code"] if ct else "",
            "name": ct["name"] if ct else "",
            "category": ct["category"] if ct else "",
            "issuing_org": ct["issuing_org"] if ct else "",
            "parent_id": ct["parent_id"] if ct else None,
            "tags": list(ct["tags"]) if ct else [],
            "is_medical": ct["is_medical"] if ct else False,
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


def list_qualifications() -> list[dict]:
    """Return qualification profiles (code, name, any_tags, all_tags, min_level)
    from the master catalog (`/api/master/qualification-types`, see
    data/db/sarapp_db/api/routers/qualification_types.py)."""
    try:
        return api_client.get(_QUALIFICATIONS_BASE) or []
    except Exception:
        return []


def qualifications_met(certs: list[dict], catalog_by_id: dict[int, dict] | None = None) -> list[dict]:
    """Return the qualification rows a set of certs satisfies.

    `certs` is a list of `{cert_type_id, level}` — the highest level per cert
    is considered, same rule a saved personnel record's certifications and a
    dialog's in-progress (unsaved) edits both follow. Pure/local: no
    personnel lookup, so a UI editing a person's certs before saving can show
    qualifications met from its own in-memory state rather than only after
    the record is written back.

    Rules per qualification: cert's level >= qualification's min_level, cert
    has all of `all_tags` (if any), and at least one of `any_tags` (if any).
    """
    if catalog_by_id is None:
        catalog_by_id = {ct["id"]: ct for ct in list_catalog()}

    max_levels: dict[int, int] = {}
    for c in certs or []:
        try:
            cid = int(c.get("cert_type_id"))
            lvl = int(c.get("level") or 0)
        except (TypeError, ValueError):
            continue
        max_levels[cid] = max(max_levels.get(cid, 0), lvl)

    met: list[dict] = []
    for qualification in list_qualifications():
        min_level = int(qualification.get("min_level") or 2)
        all_tags = set(qualification.get("all_tags") or [])
        any_tags = set(qualification.get("any_tags") or [])
        for cert_type_id, lvl in max_levels.items():
            if lvl < min_level:
                continue
            tags: set[str] = set(catalog_by_id.get(cert_type_id, {}).get("tags") or [])
            if all_tags and not all_tags.issubset(tags):
                continue
            if any_tags and not (tags & any_tags):
                continue
            met.append(qualification)
            break
    return met


__all__ = [
    "list_catalog",
    "list_personnel_certs",
    "set_personnel_cert",
    "delete_personnel_cert",
    "list_tags_for_cert",
    "list_qualifications",
    "qualifications_met",
]
