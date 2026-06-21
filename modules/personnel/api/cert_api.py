"""Personnel certification API for UI usage.

This API reads the catalog from the MongoDB master DB and permits editing
of personnel certification levels and attachments.
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
    """Return the person's certifications from the API."""
    try:
        return api_client.get(f"/api/master/certifications/personnel/{personnel_id}") or []
    except Exception:
        return []


def set_personnel_cert(
    personnel_id: int,
    cert_type_id: int,
    level: int,
    attachment_url: str | None,
) -> None:
    """Insert or update a person's certification record via API."""
    try:
        lvl = max(0, min(3, int(level)))
        api_client.post(
            f"/api/master/certifications/personnel/{personnel_id}/{cert_type_id}",
            json={"level": lvl, "attachment_url": attachment_url},
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

    conn = _conn()
    try:
        sql = (
            "WITH max_levels AS ("
            "  SELECT certification_type_id, MAX(level) AS lvl"
            "  FROM personnel_certifications"
            "  WHERE personnel_id = ?"
            "  GROUP BY certification_type_id"
            ")"
            " SELECT ct.id, ct.code, ml.lvl, t.tag"
            " FROM max_levels ml"
            " JOIN certification_types ct ON ct.id = ml.certification_type_id"
            " LEFT JOIN cert_tags t ON t.certification_type_id = ct.id"
        )
        cur = conn.execute(sql, (int(personnel_id),))
        # Build map of cert -> {level, tags}
        cert_map: dict[int, dict[str, Any]] = {}
        for row in cur.fetchall():
            cid = int(row[0])
            lvl = int(row[2] or 0)
            tag = row[3]
            entry = cert_map.setdefault(cid, {"level": lvl, "tags": set()})
            entry["level"] = max(entry["level"], lvl)
            if tag is not None:
                entry["tags"].add(str(tag))

        # Evaluate profile
        for info in cert_map.values():
            lvl = int(info["level"])
            if lvl < prof.min_level:
                continue
            tags: set[str] = set(info["tags"])  # type: ignore[assignment]
            # Must include all required tags if specified
            if prof.all_tags and not all(t in tags for t in prof.all_tags):
                continue
            # Must include at least one from any_tags if specified
            if prof.any_tags and not any(t in tags for t in prof.any_tags):
                continue
            # Passed
            return True
        return False
    finally:
        conn.close()


# Guard catalog writes (not exposed here, but ensure consistency if added later)
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
