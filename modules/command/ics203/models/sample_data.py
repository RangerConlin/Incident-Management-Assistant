from __future__ import annotations

"""Seed data and organizational templates for ICS-203."""

import re
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


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------


class TemplateBuilder:
    """Utility for assembling hierarchical template definitions."""

    def __init__(self) -> None:
        self._items: list[SeedItem] = []
        self._unit_aliases: dict[str, int] = {}
        self._unit_count = 0

    # ------------------------------------------------------------------
    def add_unit(
        self,
        unit_type: str,
        name: str,
        *,
        alias: str | None = None,
        parent: str | None = None,
        sort_order: int = 0,
    ) -> "TemplateBuilder":
        parent_placeholder: int | None = None
        if parent is not None:
            parent_placeholder = self._placeholder_for_alias(parent)
        unit = OrgUnit(
            id=None,
            incident_id="{iid}",
            unit_type=unit_type,
            name=name,
            parent_unit_id=parent_placeholder,
            sort_order=sort_order,
        )
        self._items.append(("unit", unit))
        self._unit_count += 1
        key = self._normalize_alias(alias or name)
        if key in self._unit_aliases:
            raise ValueError(f"Duplicate template alias '{alias or name}'")
        self._unit_aliases[key] = self._unit_count
        return self

    # ------------------------------------------------------------------
    def add_position(
        self,
        title: str,
        *,
        unit: str | None = None,
        sort_order: int = 0,
    ) -> "TemplateBuilder":
        unit_placeholder: int | None = None
        if unit is not None:
            unit_placeholder = self._placeholder_for_alias(unit)
        position = Position(
            id=None,
            incident_id="{iid}",
            title=title,
            unit_id=unit_placeholder,
            sort_order=sort_order,
        )
        self._items.append(("position", position))
        return self

    # ------------------------------------------------------------------
    def build(self) -> Sequence[SeedItem]:
        return tuple(self._items)

    # ------------------------------------------------------------------
    def _placeholder_for_alias(self, alias: str) -> int:
        key = self._normalize_alias(alias)
        try:
            index = self._unit_aliases[key]
        except KeyError as exc:  # pragma: no cover - developer misuse
            raise ValueError(f"Unknown template alias '{alias}'") from exc
        return -index

    @staticmethod
    def _normalize_alias(alias: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", alias.strip().lower())


def _template_operations_branch() -> Sequence[SeedItem]:
    builder = TemplateBuilder()
    builder.add_unit("Section", "Operations", alias="operations", sort_order=0)
    builder.add_unit(
        "Branch",
        "Branch I",
        alias="branch_i",
        parent="operations",
        sort_order=1,
    )
    builder.add_unit(
        "Division",
        "Division Alpha",
        alias="division_alpha",
        parent="branch_i",
        sort_order=0,
    )
    builder.add_unit(
        "Division",
        "Division Bravo",
        alias="division_bravo",
        parent="branch_i",
        sort_order=1,
    )
    builder.add_position("Branch Director", unit="branch_i", sort_order=0)
    builder.add_position(
        "Division Supervisor (Alpha)", unit="division_alpha", sort_order=0
    )
    builder.add_position(
        "Division Supervisor (Bravo)", unit="division_bravo", sort_order=1
    )
    builder.add_position("Staging Area Manager", unit="operations", sort_order=5)
    return builder.build()


def _template_air_operations() -> Sequence[SeedItem]:
    builder = TemplateBuilder()
    builder.add_unit("Section", "Operations", alias="operations", sort_order=0)
    builder.add_unit(
        "Branch",
        "Air Operations Branch",
        alias="air_branch",
        parent="operations",
        sort_order=2,
    )
    builder.add_unit(
        "Group",
        "Air Tactical Group",
        alias="air_tactical",
        parent="air_branch",
        sort_order=0,
    )
    builder.add_unit(
        "Group",
        "Air Support Group",
        alias="air_support",
        parent="air_branch",
        sort_order=1,
    )
    builder.add_position("Air Operations Branch Director", unit="air_branch")
    builder.add_position("Air Tactical Group Supervisor", unit="air_tactical")
    builder.add_position("Air Support Group Supervisor", unit="air_support")
    builder.add_position("Helibase Manager", unit="air_support", sort_order=1)
    return builder.build()


def _template_planning_units() -> Sequence[SeedItem]:
    builder = TemplateBuilder()
    builder.add_unit("Section", "Planning", alias="planning", sort_order=0)
    builder.add_unit(
        "Group",
        "Resources Unit",
        alias="resources_unit",
        parent="planning",
        sort_order=0,
    )
    builder.add_unit(
        "Group",
        "Situation Unit",
        alias="situation_unit",
        parent="planning",
        sort_order=1,
    )
    builder.add_unit(
        "Group",
        "Demobilization Unit",
        alias="demobilization_unit",
        parent="planning",
        sort_order=2,
    )
    builder.add_unit(
        "Group",
        "Documentation Unit",
        alias="documentation_unit",
        parent="planning",
        sort_order=3,
    )
    builder.add_position("Resources Unit Leader", unit="resources_unit")
    builder.add_position("Situation Unit Leader", unit="situation_unit")
    builder.add_position("Demobilization Unit Leader", unit="demobilization_unit")
    builder.add_position("Documentation Unit Leader", unit="documentation_unit")
    builder.add_position("Technical Specialist", unit="planning", sort_order=10)
    return builder.build()


def _template_logistics_branches() -> Sequence[SeedItem]:
    builder = TemplateBuilder()
    builder.add_unit("Section", "Logistics", alias="logistics", sort_order=0)
    builder.add_unit(
        "Branch",
        "Service Branch",
        alias="service_branch",
        parent="logistics",
        sort_order=0,
    )
    builder.add_unit(
        "Branch",
        "Support Branch",
        alias="support_branch",
        parent="logistics",
        sort_order=1,
    )
    builder.add_unit(
        "Group",
        "Communications Unit",
        alias="communications_unit",
        parent="service_branch",
        sort_order=0,
    )
    builder.add_unit(
        "Group",
        "Medical Unit",
        alias="medical_unit",
        parent="service_branch",
        sort_order=1,
    )
    builder.add_unit(
        "Group",
        "Food Unit",
        alias="food_unit",
        parent="service_branch",
        sort_order=2,
    )
    builder.add_unit(
        "Group",
        "Supply Unit",
        alias="supply_unit",
        parent="support_branch",
        sort_order=0,
    )
    builder.add_unit(
        "Group",
        "Facilities Unit",
        alias="facilities_unit",
        parent="support_branch",
        sort_order=1,
    )
    builder.add_unit(
        "Group",
        "Ground Support Unit",
        alias="ground_support_unit",
        parent="support_branch",
        sort_order=2,
    )
    builder.add_position("Service Branch Director", unit="service_branch")
    builder.add_position("Support Branch Director", unit="support_branch")
    builder.add_position("Communications Unit Leader", unit="communications_unit")
    builder.add_position("Medical Unit Leader", unit="medical_unit")
    builder.add_position("Food Unit Leader", unit="food_unit")
    builder.add_position("Supply Unit Leader", unit="supply_unit")
    builder.add_position("Facilities Unit Leader", unit="facilities_unit")
    builder.add_position("Ground Support Unit Leader", unit="ground_support_unit")
    return builder.build()


def _template_command_staff() -> Sequence[SeedItem]:
    builder = TemplateBuilder()
    builder.add_unit("Command", "Command", alias="command", sort_order=0)
    builder.add_position("Incident Commander", sort_order=0)
    builder.add_position("Deputy Incident Commander", sort_order=1)
    builder.add_position("Safety Officer", sort_order=2)
    builder.add_position("Public Information Officer", sort_order=3)
    builder.add_position("Liaison Officer", sort_order=4)
    builder.add_position("Agency Representative", unit="command", sort_order=5)
    return builder.build()


TEMPLATES: Dict[str, Sequence[SeedItem]] = {
    "Command Staff": _template_command_staff(),
    "Logistics → Service & Support Branches": _template_logistics_branches(),
    "Operations → Air Operations Branch": _template_air_operations(),
    "Operations → Branch I → Alpha/Bravo": _template_operations_branch(),
    "Planning → Section Units": _template_planning_units(),
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
