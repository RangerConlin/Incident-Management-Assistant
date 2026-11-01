"""Shared helpers for rendering a personnel display name with rank attached.

Personnel records store a free-text ``rank`` field (see
``modules/personnel/catalog_io.py``). The personnel editor
(``ui/personnel/ui_personnel.py``) populates that field from the active
rank catalog's "short display" abbreviation (e.g. "Capt", "LT", "Sgt") when
one is available, so the stored value is normally already the compact form
we want to show. This module centralizes the "<rank> <name>" formatting so
status boards and form exports render the same way instead of each call
site re-implementing it (or forgetting rank entirely).
"""

from __future__ import annotations

from typing import Any

__all__ = ["format_name_with_rank"]


def format_name_with_rank(name: str | None, rank: str | None) -> str:
    """Return ``name`` prefixed with ``rank`` for display, e.g. "Capt Jane Smith".

    - If ``rank`` is empty/whitespace, the bare name is returned unchanged.
    - If ``name`` is empty/whitespace, the bare rank (or "") is returned.
    - Leading/trailing whitespace on either input is trimmed; a rank that
      already ends with the name (e.g. a pre-formatted value) is not
      re-prefixed, to avoid "Capt Capt Jane Smith" style duplication.

    This performs no catalog lookups - it formats whatever rank string is
    already stored on the personnel record (which, per the editor UI, is
    already the catalog's short-display abbreviation when one was picked
    from the rank dropdown). Callers that only have a bare personnel dict
    should use :func:`personnel_display_name` instead.
    """

    clean_name = (name or "").strip()
    clean_rank = (rank or "").strip()
    if not clean_rank:
        return clean_name
    if not clean_name:
        return clean_rank
    if clean_name.lower().startswith(clean_rank.lower() + " "):
        # Already prefixed (e.g. name field itself already carries the rank).
        return clean_name
    return f"{clean_rank} {clean_name}"


def personnel_display_name(person: dict[str, Any] | None) -> str:
    """Convenience wrapper: build the rank-prefixed display name from a
    personnel-shaped dict with ``name``/``full_name`` and ``rank`` keys.
    """

    if not person:
        return ""
    name = person.get("name") or person.get("full_name") or ""
    rank = person.get("rank") or ""
    return format_name_with_rank(name, rank)
