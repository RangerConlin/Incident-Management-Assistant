from __future__ import annotations

"""Seed data and organizational templates for ICS-203."""

from typing import Dict, List, Sequence, Tuple

from .models import OrgUnit, Position

SeedItem = Tuple[str, OrgUnit | Position]


def seed_units_and_positions(incident_id: str | int) -> List[SeedItem]:
    """Return a conservative seed set for brand new incidents."""

    iid = str(incident_id)
    return [
        ("unit", OrgUnit(None, iid, "Command", "Command", None, 0)),
        ("unit", OrgUnit(None, iid, "Section", "Operations", None, 1)),
        ("unit", OrgUnit(None, iid, "Section", "Planning", None, 2)),
        ("unit", OrgUnit(None, iid, "Section", "Logistics", None, 3)),
        ("unit", OrgUnit(None, iid, "Section", "Finance/Admin", None, 4)),
        ("position", Position(None, iid, "Incident Commander", None, 0)),
        ("position", Position(None, iid, "Deputy Incident Commander", None, 1)),
        ("position", Position(None, iid, "Operations Section Chief", None, 2)),
        ("position", Position(None, iid, "Planning Section Chief", None, 3)),
        ("position", Position(None, iid, "Logistics Section Chief", None, 4)),
        ("position", Position(None, iid, "Finance/Admin Section Chief", None, 5)),
        ("position", Position(None, iid, "Safety Officer", None, 6)),
        ("position", Position(None, iid, "Public Information Officer", None, 7)),
        ("position", Position(None, iid, "Liaison Officer", None, 8)),
    ]


TEMPLATES: Dict[str, Sequence[SeedItem]] = {
    "Operations → Branch I → Alpha/Bravo": [
        ("unit", OrgUnit(None, "{iid}", "Section", "Operations", None, 0)),
        ("unit", OrgUnit(None, "{iid}", "Branch", "Branch I", -1, 1)),
        ("unit", OrgUnit(None, "{iid}", "Division", "Division Alpha", -2, 2)),
        ("unit", OrgUnit(None, "{iid}", "Division", "Division Bravo", -2, 3)),
        ("position", Position(None, "{iid}", "Division Supervisor", -2, 0)),
    ],
    "Planning Support": [
        ("unit", OrgUnit(None, "{iid}", "Section", "Planning", None, 0)),
        ("position", Position(None, "{iid}", "Resources Unit Leader", None, 0)),
        ("position", Position(None, "{iid}", "Situation Unit Leader", None, 1)),
    ],
}


def render_template(name: str, incident_id: str | int) -> List[SeedItem]:
    """Return seed items for ``name`` with the incident id injected."""

    iid = str(incident_id)
    pattern = TEMPLATES.get(name)
    if not pattern:
        return []
    rendered: List[SeedItem] = []
    for kind, obj in pattern:
        if isinstance(obj, OrgUnit):
            rendered.append(
                (
                    kind,
                    OrgUnit(
                        id=None,
                        incident_id=iid,
                        unit_type=obj.unit_type,
                        name=obj.name,
                        parent_unit_id=obj.parent_unit_id,
                        sort_order=obj.sort_order,
                    ),
                )
            )
        elif isinstance(obj, Position):
            rendered.append(
                (
                    kind,
                    Position(
                        id=None,
                        incident_id=iid,
                        title=obj.title,
                        unit_id=obj.unit_id,
                        sort_order=obj.sort_order,
                    ),
                )
            )
    return rendered
