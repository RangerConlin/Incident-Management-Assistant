"""Canonical ICS position catalog for meeting attendee role selection.

This is the authoritative list of every position that could attend a meeting,
organized by ICS section/group. It serves as the core for position-based
permissions, messaging routing, and any other position-aware logic.

Positions are deliberately hardcoded so the program has a known, stable
catalog regardless of the current incident's live organization chart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class IcsPosition:
    """A single position entry in the ICS position catalog."""

    name: str
    group: str
    """Section/group label for UI grouping, e.g. 'Command Staff', 'Planning Section'."""


# ── The master position list ─────────────────────────────────────────────

ICS_POSITIONS: list[IcsPosition] = [
    # ── Command Staff ────────────────────────────────────────────────────
    IcsPosition(name="Incident Commander", group="Command Staff"),
    IcsPosition(name="Safety Officer", group="Command Staff"),
    IcsPosition(name="Public Information Officer", group="Command Staff"),
    IcsPosition(name="Liaison Officer", group="Command Staff"),
    # ── Operations Section ──────────────────────────────────────────────
    IcsPosition(name="Operations Section Chief", group="Operations Section"),
    IcsPosition(name="Staging Area Manager", group="Operations Section"),
    IcsPosition(name="Air Operations Branch Director", group="Operations Section"),
    IcsPosition(name="Ground Operations Branch Director", group="Operations Section"),
    IcsPosition(name="Branch Director", group="Operations Section"),
    IcsPosition(name="Division/Group Supervisor", group="Operations Section"),
    IcsPosition(name="Helibase Manager", group="Operations Section"),
    IcsPosition(name="Air Support Group Supervisor", group="Operations Section"),
    IcsPosition(name="Operations Supervisor", group="Operations Section"),
    # ── Planning Section ────────────────────────────────────────────────
    IcsPosition(name="Planning Section Chief", group="Planning Section"),
    IcsPosition(name="Resources Unit Leader", group="Planning Section"),
    IcsPosition(name="Situation Unit Leader", group="Planning Section"),
    IcsPosition(name="Documentation Unit Leader", group="Planning Section"),
    IcsPosition(name="Demobilization Unit Leader", group="Planning Section"),
    # ── Logistics Section ────────────────────────────────────────────────
    IcsPosition(name="Logistics Section Chief", group="Logistics Section"),
    IcsPosition(name="Service Branch Director", group="Logistics Section"),
    IcsPosition(name="Support Branch Director", group="Logistics Section"),
    IcsPosition(name="Communications Unit Leader", group="Logistics Section"),
    IcsPosition(name="Medical Unit Leader", group="Logistics Section"),
    IcsPosition(name="Food Unit Leader", group="Logistics Section"),
    IcsPosition(name="Supply Unit Leader", group="Logistics Section"),
    IcsPosition(name="Facilities Unit Leader", group="Logistics Section"),
    IcsPosition(name="Ground Support Unit Leader", group="Logistics Section"),
    # ── Finance/Admin Section ────────────────────────────────────────────
    IcsPosition(name="Finance/Administration Section Chief", group="Finance/Admin Section"),
    IcsPosition(name="Time Unit Leader", group="Finance/Admin Section"),
    IcsPosition(name="Procurement Unit Leader", group="Finance/Admin Section"),
    IcsPosition(name="Compensation/Claims Unit Leader", group="Finance/Admin Section"),
    IcsPosition(name="Cost Unit Leader", group="Finance/Admin Section"),
    # ── Intelligence / Investigations Section ────────────────────────────
    IcsPosition(name="Intelligence Section Chief", group="Intelligence/Investigations Section"),
    IcsPosition(name="Intel/Investigations Supervisor", group="Intelligence/Investigations Section"),
    # ── Additional ICS Roles ─────────────────────────────────────────────
    IcsPosition(name="Agency Representative", group="Additional ICS Roles"),
    IcsPosition(name="Technical Specialist", group="Additional ICS Roles"),
    IcsPosition(name="Subject Matter Expert", group="Additional ICS Roles"),
    IcsPosition(name="Command Staff (Generic)", group="Additional ICS Roles"),
    IcsPosition(name="General Staff (Generic)", group="Additional ICS Roles"),
    IcsPosition(name="Section Chief (Generic)", group="Additional ICS Roles"),
]


# ── Lookup helpers ───────────────────────────────────────────────────────


def position_names_by_group() -> dict[str, list[str]]:
    """Return positions grouped by their section label.

    Returns:
        dict mapping group name -> sorted list of position names in that group.
    """
    groups: dict[str, list[str]] = {}
    for pos in ICS_POSITIONS:
        groups.setdefault(pos.group, []).append(pos.name)
    return groups


def all_position_names() -> list[str]:
    """Return every position name in the catalog."""
    return [p.name for p in ICS_POSITIONS]


__all__ = [
    "ICS_POSITIONS",
    "IcsPosition",
    "all_position_names",
    "position_names_by_group",
]