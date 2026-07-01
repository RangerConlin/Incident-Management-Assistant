"""Certification catalog sync — MongoDB-backed via API."""

from __future__ import annotations

from typing import Any

from modules.personnel.models.cert_catalog import CATALOG, CATALOG_VERSION


_SYNC_FIELDS = ("code", "name", "category", "issuing_org", "parent_id", "is_medical")


def _body_for_cert(ct) -> dict[str, Any]:
    return {
        "cert_type_id": ct.id,
        "code": ct.code,
        "name": ct.name,
        "category": ct.category,
        "issuing_org": ct.issuing_org,
        "parent_id": ct.parent_id,
        "tags": list(ct.tags),
        "is_medical": bool(ct.is_medical),
    }


def _needs_update(current: dict[str, Any], desired: dict[str, Any]) -> bool:
    for field in _SYNC_FIELDS:
        if current.get(field) != desired.get(field):
            return True
    return set(current.get("tags") or []) != set(desired.get("tags") or [])


def sync() -> tuple[bool, str]:
    """Sync the hardcoded certification catalog into MongoDB via the API.

    Returns (changed: bool, message: str) for UI display.
    """
    try:
        from utils.api_client import api_client
        existing = {
            int(t["id"]): t
            for t in (api_client.get("/api/master/certifications/types") or [])
            if t.get("id") is not None
        }
    except Exception as exc:
        return False, f"Could not reach certification API: {exc}"

    changed = False
    for ct in CATALOG:
        body = _body_for_cert(ct)
        if ct.id not in existing:
            try:
                api_client.post("/api/master/certifications/types", json=body)
                changed = True
            except Exception:
                pass
        else:
            current = existing[ct.id]
            if _needs_update(current, body):
                try:
                    api_client.put(f"/api/master/certifications/types/{ct.id}", json=body)
                    changed = True
                except Exception:
                    pass

    if changed:
        return True, f"Certification catalog updated to {CATALOG_VERSION}"
    return False, f"Certification catalog already at {CATALOG_VERSION}"


__all__ = ["sync"]
