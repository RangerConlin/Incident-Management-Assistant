"""Models for Resource Packages (Stage 3).

A Resource Package is a reusable collection of personnel/vehicles/aircraft/
equipment that routinely respond together (a CAP ground team, a fire engine
company, an ambulance, a patrol unit) -- a standing roster definition, not
an incident team. It must always be saveable while incomplete/understaffed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

MEMBERSHIP_KINDS: tuple[str, ...] = ("fixed", "preferred", "optional")
RESOURCE_KINDS: tuple[str, ...] = ("personnel", "vehicle", "aircraft", "equipment")


@dataclass(slots=True)
class PackageResourceRef:
    resource_type: str
    resource_id: int
    membership: str = "fixed"  # fixed | preferred | optional
    role: str = ""  # free-text label, e.g. "Team Leader", "Driver"
    label: str = ""  # display label resolved client-side, not persisted


@dataclass(slots=True)
class RequiredPosition:
    """A role/qualification the package needs, without naming a specific person."""

    role: str
    qualification: str = ""
    quantity: int = 1
    notes: str = ""


@dataclass(slots=True)
class MinimumQuantityRequirement:
    """e.g. "4 qualified personnel", "2 vehicles"."""

    description: str
    resource_kind: str = ""  # personnel | vehicle | aircraft | equipment | "" (any)
    qualification: str = ""
    minimum_count: int = 1


@dataclass(slots=True)
class ResourcePackage:
    name: str
    description: str = ""
    owning_organization: str = ""
    parent_org_unit: Optional[str] = None
    linked_resource_type_id: Optional[int] = None
    default_team_designation: str = ""
    resources: list[PackageResourceRef] = field(default_factory=list)
    required_positions: list[RequiredPosition] = field(default_factory=list)
    minimum_quantities: list[MinimumQuantityRequirement] = field(default_factory=list)
    is_active: bool = True
    notes: str = ""
    id: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    personnel_count: int = 0
    vehicle_count: int = 0
    aircraft_count: int = 0
    equipment_count: int = 0
    asset_count: int = 0

    def resources_of(self, resource_type: str) -> list[PackageResourceRef]:
        return [r for r in self.resources if r.resource_type == resource_type]
