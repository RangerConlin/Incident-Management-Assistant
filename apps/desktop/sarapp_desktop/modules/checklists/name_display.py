"""Desktop-side mirror of the server's
``sarapp_db.services.checklist_service.format_person_display``.

Kept as a tiny, dependency-free duplicate (not an import across the
process boundary, since the desktop and server are separate deployables)
so a checklist's "Completed by J. Smith" caption renders identically to
how the server formats the same name into ICS-214 entry text. There is no
"J. Smith"-style formatter anywhere else in this desktop app — the
existing `utils/personnel_display.py` produces "<rank> <full name>"
instead, which is a different convention for a different context (rank
boards), not item-level checklist attribution.
"""

from __future__ import annotations

__all__ = ["format_person_display"]


def format_person_display(first_name: str | None, last_name: str | None, fallback: str = "") -> str:
    first = (first_name or "").strip()
    last = (last_name or "").strip()
    if last:
        initial = f"{first[0]}." if first else ""
        return f"{initial} {last}".strip()
    return fallback
