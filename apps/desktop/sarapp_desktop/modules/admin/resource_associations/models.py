"""Models for standing Resource Associations (Stage 2).

A Resource Association is a persistent relationship between two individual
master resources -- e.g. a radio assigned to a person, equipment carried
onboard a vehicle, a vehicle associated with a trailer. It is never
incident-specific: changing an incident team's composition must never
create, edit, or remove one of these.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Kinds of individual master resource an association can reference.
RESOURCE_KINDS: tuple[str, ...] = ("personnel", "vehicle", "aircraft", "equipment")

# Suggested association types shown in the picker. `association_type` is a
# free-text field everywhere it is stored -- this list is UI convenience
# only, never a validation constraint, so a new relationship kind never
# needs a code change.
SUGGESTED_ASSOCIATION_TYPES: tuple[str, ...] = (
    "Assigned",
    "Carried/Onboard",
    "Default Member",
    "Associated",
)


@dataclass(slots=True)
class ResourceEndpoint:
    resource_type: str
    resource_id: int
    label: str = ""


@dataclass(slots=True)
class ResourceAssociation:
    source: ResourceEndpoint
    target: ResourceEndpoint
    association_type: str = "Associated"
    owning_organization: Optional[str] = None
    effective_start: Optional[str] = None
    effective_end: Optional[str] = None
    notes: str = ""
    active: bool = True
    id: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
