"""Team readiness validation and resource-conflict detection (Stage 6).

This module is the **sole authoritative source** for evaluating an
incident team's readiness against its linked Resource Type Library
definition. No prior GT/UDF/UAS/AIR hardcoded readiness rules existed
anywhere in this codebase before this module -- team_type was previously
an unconstrained free string with no validation logic attached to it at
all (see docs/archive/design-documents/Instructions/database_architecture.md's
"Team Builder (Stage 5)" section and agents.md's migration-status notes).
Any future readiness rule belongs here, not duplicated elsewhere.

Deliberately framework- and database-free: everything here is plain
dataclasses and pure functions so it can be unit tested without MongoDB.
The router (`resource_validation.py`) does all the Mongo reads and hands
this module already-resolved data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

READY = "Ready"
READY_WITH_LIMITATIONS = "Ready with Limitations"
NOT_READY = "Not Ready"
NOT_EVALUATED = "Not Evaluated"

OUTCOMES: tuple[str, ...] = (READY, READY_WITH_LIMITATIONS, NOT_READY, NOT_EVALUATED)


@dataclass
class RequirementSpec:
    """Requirements pulled from a linked Resource Type Library entry."""

    min_personnel: Optional[int] = None
    required_qualifications: list[str] = field(default_factory=list)
    # Resource Type Library ids an assigned vehicle/aircraft/equipment item
    # must belong to (its own `resource_type_id`).
    required_equipment_type_ids: list[int] = field(default_factory=list)


@dataclass
class TeamComposition:
    """The team's *actual* assembled composition -- never assumed package
    completeness; always read from the team's own live assignment."""

    personnel_ids: list[int] = field(default_factory=list)
    # person_id -> the qualification names/codes that person holds.
    personnel_qualifications: dict[int, set[str]] = field(default_factory=dict)
    vehicle_ids: list[int] = field(default_factory=list)
    aircraft_ids: list[int] = field(default_factory=list)
    equipment_ids: list[int] = field(default_factory=list)
    # The Resource Type Library id each assigned vehicle/aircraft/equipment
    # item itself belongs to, when known.
    assigned_resource_type_ids: list[int] = field(default_factory=list)
    # Human-readable conflict descriptions (Stage 6 conflict prevention);
    # any non-empty list here forces Not Ready regardless of staffing.
    conflicts: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    outcome: str
    messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"outcome": self.outcome, "messages": list(self.messages)}


def evaluate_team(requirements: Optional[RequirementSpec], composition: TeamComposition) -> ValidationResult:
    """Evaluate a team's actual composition against its requirements.

    Outcomes:
        Not Ready -- a resource conflict exists, the team is short of its
            minimum staffing, or a required equipment type is missing.
        Ready with Limitations -- staffing/equipment minimums are met but
            one or more required qualifications aren't held by anyone
            assigned.
        Ready -- every requirement is met.
        Not Evaluated -- no Resource Type Library definition is linked, so
            there is nothing to evaluate against.
    """
    if composition.conflicts:
        return ValidationResult(outcome=NOT_READY, messages=list(composition.conflicts))

    if requirements is None:
        return ValidationResult(
            outcome=NOT_EVALUATED,
            messages=["No Resource Type Library definition is linked to this team; readiness cannot be evaluated."],
        )

    messages: list[str] = []
    hard_shortfall = False

    personnel_count = len(composition.personnel_ids)
    if requirements.min_personnel is not None and personnel_count < requirements.min_personnel:
        missing = requirements.min_personnel - personnel_count
        messages.append(
            f"Requires {missing} additional personnel (has {personnel_count} of {requirements.min_personnel} minimum)."
        )
        hard_shortfall = True

    held_qualifications: set[str] = set()
    for quals in composition.personnel_qualifications.values():
        held_qualifications.update(q.strip().lower() for q in quals if q)
    unmet_qualifications = [
        q for q in requirements.required_qualifications if q.strip().lower() not in held_qualifications
    ]
    for qualification in unmet_qualifications:
        messages.append(f"Requires one additional qualified {qualification}.")

    missing_equipment_types = [
        type_id
        for type_id in requirements.required_equipment_type_ids
        if type_id not in composition.assigned_resource_type_ids
    ]
    if missing_equipment_types:
        messages.append(
            "Missing required equipment/vehicle/aircraft of resource type id(s): "
            + ", ".join(str(t) for t in missing_equipment_types) + "."
        )
        hard_shortfall = True

    if not messages:
        return ValidationResult(
            outcome=READY, messages=["All staffing, qualification, and equipment requirements are met."]
        )
    if hard_shortfall:
        return ValidationResult(outcome=NOT_READY, messages=messages)
    return ValidationResult(outcome=READY_WITH_LIMITATIONS, messages=messages)


def find_conflicting_assignments(
    this_team_id: Optional[int],
    this_team_refs: list[tuple[str, int]],
    other_teams: list[dict],
) -> list[str]:
    """A vehicle/person/serialized-equipment item cannot be simultaneously
    committed to two different *active* incident team assignments.

    `other_teams` is `[{"team_id": int, "disbanded": bool, "status": str,
    "refs": [(resource_type, resource_id), ...]}, ...]` for every other
    team in the same incident. Disbanded teams never conflict -- their
    resources are free. Being named in several *packages'* standing
    membership is never checked here at all (packages are not teams), so
    it is never flagged as a conflict.
    """
    conflicts: list[str] = []
    this_set = set(this_team_refs)
    for other in other_teams:
        if other.get("team_id") == this_team_id:
            continue
        if other.get("disbanded"):
            continue
        overlap = this_set & set(other.get("refs") or [])
        for resource_type, resource_id in sorted(overlap):
            conflicts.append(
                f"{resource_type.capitalize()} {resource_id} is already committed to team "
                f"{other.get('team_name') or other.get('team_id')}."
            )
    return conflicts
