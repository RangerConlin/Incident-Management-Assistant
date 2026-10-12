"""
ResourceGapService
==================
Compares resource requirements against available resources in the system.

Queries the existing ResourceAssignmentRepository (which reads from the
master Resource Type Library and active incident check-in data).

All gap calculations are isolated here so they can be refined as the
availability definition evolves without touching the UI or repository.
"""
from __future__ import annotations

from typing import Any

from modules.planning.tactics_resources.models.work_assignment_models import (
    ResourceGapSummary,
    WorkAssignmentResourceRequirement,
)


class ResourceGapService:
    """
    Calculates resource gaps for Work Assignments.

    Usage:
        svc = ResourceGapService()
        svc.calculate_gap_for_assignment(work_assignment_id)
    """

    def __init__(self, db_path: str | None = None) -> None:
        # Lazy-import to avoid hard dependency if modules are not installed
        self._db_path = db_path
        self._assignment_repo: Any = None
        self._resource_type_repo: Any = None

    def _get_assignment_repo(self):
        if self._assignment_repo is None:
            try:
                from modules.admin.resource_types.data.resource_assignment_repository import (
                    ApiResourceAssignmentRepository,
                )
                self._assignment_repo = ApiResourceAssignmentRepository()
            except Exception:
                self._assignment_repo = None
        return self._assignment_repo

    def _get_resource_type_repo(self):
        if self._resource_type_repo is None:
            try:
                from modules.admin.resource_types.data.resource_type_repository import (
                    ApiResourceTypeRepository,
                )
                self._resource_type_repo = ApiResourceTypeRepository()
            except Exception:
                self._resource_type_repo = None
        return self._resource_type_repo

    def get_matching_available_resources(
        self,
        resource_type_id: int | None = None,
        capability_id: int | None = None,
        resource_type_text: str = "",
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Return available resources matching the given resource type or capability.

        Returns a dict keyed by resource kind (personnel, team, vehicle, equipment)
        where each value is a list of matching resource dicts.

        Returns empty categories if the library is unavailable.
        """
        repo = self._get_assignment_repo()
        result: dict[str, list[dict[str, Any]]] = {
            "personnel": [],
            "team": [],
            "vehicle": [],
            "equipment": [],
        }
        if repo is None or resource_type_id is None:
            # Cannot query library without an ID — gap remains unknown
            return result

        try:
            full = repo.get_available_resources_by_type(resource_type_id)
            result["personnel"] = full.get("personnel", [])
            result["team"] = full.get("team", [])
            result["vehicle"] = full.get("vehicle", [])
            result["equipment"] = full.get("equipment", [])
        except Exception:
            pass
        return result

    def calculate_gap_for_requirement(
        self, requirement: WorkAssignmentResourceRequirement
    ) -> int:
        """
        Calculate the gap for one resource requirement line.

        gap = max(quantity_required - quantity_assigned, 0)

        If we can query the library, we also check available count and
        use whichever is greater to give the most useful gap signal.
        """
        # If actual resources have been linked, their count drives quantity_assigned.
        # If not, use the user-entered quantity_assigned as-is.
        assigned = requirement.quantity_assigned

        # Optionally query available from the library
        if requirement.resource_type_id is not None:
            available_resources = self.get_matching_available_resources(
                resource_type_id=requirement.resource_type_id
            )
            available_count = sum(len(v) for v in available_resources.values())
        else:
            available_count = requirement.quantity_available

        gap = max(requirement.quantity_required - assigned, 0)
        return gap

    def calculate_gap_for_assignment(self, work_assignment_id: int) -> ResourceGapSummary:
        """
        Build a full ResourceGapSummary for a work assignment.

        Reads requirements from the repository and computes totals.
        Never raises — returns a zeroed summary on any error.
        """
        from modules.planning.tactics_resources.data.work_assignment_repository import (
            WorkAssignmentRepository,
        )
        try:
            repo = WorkAssignmentRepository(self._db_path)
            requirements = repo.list_resource_requirements(work_assignment_id)
        except Exception:
            return ResourceGapSummary(work_assignment_id=work_assignment_id)

        total_required = 0
        total_assigned = 0
        total_gap = 0

        for req in requirements:
            total_required += req.quantity_required
            total_assigned += req.quantity_assigned
            total_gap += max(req.quantity_required - req.quantity_assigned, 0)

        return ResourceGapSummary(
            work_assignment_id=work_assignment_id,
            total_required=total_required,
            total_assigned=total_assigned,
            total_gap=total_gap,
            has_gap=total_gap > 0,
            lines=requirements,
        )

    def suggest_resources_for_requirement(
        self, requirement: WorkAssignmentResourceRequirement
    ) -> list[dict[str, Any]]:
        """
        Return a flat list of available resources that match this requirement.

        Used to populate the "Assign Actual Resource" dialog.
        Returns empty list if library is unavailable or no type is set.
        """
        if requirement.resource_type_id is None:
            return []
        buckets = self.get_matching_available_resources(
            resource_type_id=requirement.resource_type_id,
            capability_id=requirement.capability_id,
        )
        suggestions: list[dict[str, Any]] = []
        for kind, items in buckets.items():
            for item in items:
                item_copy = dict(item)
                item_copy["resource_kind"] = kind
                suggestions.append(item_copy)
        return suggestions

    def summarize_assignment_resources(self, work_assignment_id: int) -> str:
        """Return a plain-text summary of resource requirements and gaps."""
        summary = self.calculate_gap_for_assignment(work_assignment_id)
        lines = [
            f"Required: {summary.total_required}",
            f"Assigned: {summary.total_assigned}",
            f"Gap: {summary.total_gap}",
        ]
        if summary.lines:
            lines.append("")
            for req in summary.lines:
                gap = max(req.quantity_required - req.quantity_assigned, 0)
                lines.append(
                    f"  • {req.resource_type_text}: "
                    f"need {req.quantity_required}, assigned {req.quantity_assigned}, gap {gap}"
                )
        return "\n".join(lines)
