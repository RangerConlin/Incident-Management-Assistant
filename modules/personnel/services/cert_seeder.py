"""Certification catalog sync — MongoDB-backed via API."""

from __future__ import annotations

from modules.personnel.models.cert_catalog import CATALOG, CATALOG_VERSION


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
        body = {
            "cert_type_id": ct.id,
            "code": ct.code,
            "name": ct.name,
            "category": ct.category,
            "issuing_org": ct.issuing_org,
            "parent_id": ct.parent_id,
            "tags": list(ct.tags),
        }
        if ct.id not in existing:
            try:
                api_client.post("/api/master/certifications/types", json=body)
                changed = True
            except Exception:
                pass
        else:
            current = existing[ct.id]
            if current.get("name") != ct.name or current.get("code") != ct.code:
                try:
                    api_client.put(f"/api/master/certifications/types/{ct.id}", json=body)
                    changed = True
                except Exception:
                    pass

    if changed:
        return True, f"Certification catalog updated to {CATALOG_VERSION}"
    return False, f"Certification catalog already at {CATALOG_VERSION}"


__all__ = ["sync"]
