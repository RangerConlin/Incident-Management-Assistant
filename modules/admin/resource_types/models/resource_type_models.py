"""Models and constants for the Resource Type Library.

These dataclasses deliberately contain no Qt code.  Keeping the data shapes
separate from the UI makes the Resource Type Library reusable by check-in,
logistics, tasking, planning, tests, and future services.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# The approved category values are kept in one place so repository validation,
# combo boxes, and future modules all use the same spelling.
RESOURCE_CATEGORIES: tuple[str, ...] = (
    "Personnel",
    "Team",
    "Vehicle",
    "Aircraft",
    "Equipment",
    "Equipment Kit / Cache",
    "Facility",
    "Supply",
    "Communications",
    "Other",
)

# Source values describe where a definition came from.  They are master-data
# metadata; they do not create any demo records by themselves.
RESOURCE_SOURCES: tuple[str, ...] = (
    "FEMA/NIMS",
    "AHJ Custom",
    "Imported",
    "Mutual Aid",
    "Temporary / Incident Only",
)


@dataclass(slots=True)
class ResourceCapability:
    """A reusable capability tag that can be attached to resource types."""

    name: str
    category: str = ""
    description: str = ""
    aliases: list[str] = field(default_factory=list)
    is_active: bool = True
    notes: str = ""
    id: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass(slots=True)
class ResourceTypeComponent:
    """A child resource type and quantity contained in a kit/cache resource."""

    parent_resource_type_id: int
    component_resource_type_id: int
    quantity: float = 1.0
    unit: str = "each"
    notes: str = ""
    required: bool = True
    id: Optional[int] = None
    component_name: str = ""
    component_category: str = ""


@dataclass(slots=True)
class FemaNimsMapping:
    """Optional FEMA/NIMS reference fields for a resource type.

    The existing names ``nims_name`` and ``type_code`` are retained for backward
    compatibility with earlier code.  The editor presents them as FEMA/NIMS
    resource name and FEMA/NIMS type.
    """

    resource_type_id: int
    nims_name: str = ""
    discipline: str = ""  # Displayed as FEMA/NIMS category in the editor.
    type_code: str = ""  # Displayed as FEMA/NIMS type in the editor.
    kind: str = ""
    reference_url: str = ""
    notes: str = ""
    typed_level: str = ""
    id: Optional[int] = None


@dataclass(slots=True)
class ResourceType:
    """Master resource type definition stored in the master database."""

    name: str
    planning_display_name: str = ""
    category: str = "Other"
    source: str = "AHJ Custom"
    owner_agency: str = ""
    description: str = ""
    default_unit: str = "each"
    typical_quantity: float = 1.0
    typical_team_size: Optional[int] = None
    is_kit_cache: bool = False
    is_consumable: bool = False
    is_active: bool = True
    notes: str = ""
    aliases: list[str] = field(default_factory=list)
    capability_ids: list[int] = field(default_factory=list)
    components: list[ResourceTypeComponent] = field(default_factory=list)
    fema_mappings: list[FemaNimsMapping] = field(default_factory=list)
    id: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""
    created_by: str = ""
    updated_by: str = ""


@dataclass(slots=True)
class ResourceTypeSearchResult:
    """Lightweight row returned by the smart free-text lookup widget."""

    resource_type_id: Optional[int]
    resource_type_text: str
    category: str = ""
    source: str = ""
    owner_agency: str = ""
    matched_on: str = ""
