"""Personnel certification API for UI usage.

This API reads the catalog mirror from the master DB and permits editing
of personnel certification levels and attachments. Direct catalog writes
are blocked in production. In developer mode, tools may regenerate the
catalog code and re-run the seeder.
"""

from __future__ import annotations

import sqlite3
from typing import List, Dict, Any, Iterable

from utils.db import get_master_conn
from utils.sqlite_helpers import enable_foreign_keys
from utils.app_settings import DEV_MODE
from modules.personnel.models.validation_profiles import PROFILES, get_profile


def _conn() -> sqlite3.Connection:
    conn = get_master_conn()
    enable_foreign_keys(conn)
    return conn


def list_catalog(filter_text: str = "", category: str | None = None) -> List[Dict[str, Any]]:
    """List catalog types from the DB mirror with optional filters.

    Returns dicts: id, code, name, category, issuing_organization, parent_id.
    """
    sql = (
        "SELECT id, code, name, category, issuing_organization, parent_certification_id AS parent_id "
        "FROM certification_types"
    )
    where: list[str] = []
    params: list[Any] = []
    if filter_text:
        where.append("(LOWER(code) LIKE ? OR LOWER(name) LIKE ?)")
        needle = f"%{filter_text.lower()}%"
        params.extend([needle, needle])
    if category:
        where.append("category = ?")
        params.append(category)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY category, code"

    conn = _conn()
    try:
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def list_tags_for_cert(cert_type_id: int) -> list[str]:
    conn = _conn()
    try:
        cur = conn.execute(
            "SELECT tag FROM cert_tags WHERE certification_type_id = ? ORDER BY tag",
            (int(cert_type_id),),
        )
        return [str(r[0]) for r in cur.fetchall()]
    finally:
        conn.close()


def list_personnel_certs(personnel_id: int) -> List[Dict[str, Any]]:
    """Return the person's certifications, joined to catalog mirror."""
    sql = (
        "SELECT pc.certification_type_id AS id, ct.code, ct.name, ct.category, "
        "pc.level, pc.attachment_url "
        "FROM personnel_certifications pc "
        "JOIN certification_types ct ON ct.id = pc.certification_type_id "
        "WHERE pc.personnel_id = ? "
        "ORDER BY ct.category, ct.code"
    )
    conn = _conn()
    try:
        cur = conn.execute(sql, (int(personnel_id),))
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def set_personnel_cert(
    personnel_id: int,
    cert_type_id: int,
    level: int,
    attachment_url: str | None,
) -> None:
    """Insert or update a person's certification record."""
    conn = _conn()
    try:
        # Enforce valid range 0..3
        lvl = max(0, min(3, int(level)))
        # If row exists, update; otherwise insert
        cur = conn.execute(
            "SELECT id FROM personnel_certifications WHERE personnel_id = ? AND certification_type_id = ?",
            (int(personnel_id), int(cert_type_id)),
        )
        row = cur.fetchone()
        if row:
            conn.execute(
                "UPDATE personnel_certifications SET level = ?, attachment_url = ? WHERE id = ?",
                (lvl, attachment_url, int(row[0])),
            )
        else:
            conn.execute(
                "INSERT INTO personnel_certifications (personnel_id, certification_type_id, level, attachment_url) "
                "VALUES (?, ?, ?, ?)",
                (int(personnel_id), int(cert_type_id), lvl, attachment_url),
            )
        conn.commit()
    finally:
        conn.close()


def delete_personnel_cert(personnel_id: int, cert_type_id: int) -> None:
    conn = _conn()
    try:
        conn.execute(
            "DELETE FROM personnel_certifications WHERE personnel_id = ? AND certification_type_id = ?",
            (int(personnel_id), int(cert_type_id)),
        )
        conn.commit()
    finally:
        conn.close()


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

