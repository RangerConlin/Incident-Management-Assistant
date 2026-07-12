from __future__ import annotations

"""Controller for incident organization management."""

from collections import defaultdict
from typing import Iterable

from .personnel_repo import ApiPersonnelPoolRepository
from .models import (
    ASSIGNMENT_TYPE_ASSISTANT,
    ASSIGNMENT_TYPE_DEPUTY,
    ASSIGNMENT_TYPE_PRIMARY,
    ASSIGNMENT_TYPE_STAFF_ASSISTANT,
    ASSIGNMENT_TYPE_TRAINEE,
    OrganizationPosition,
    OrganizationTemplate,
    OrganizationWarning,
    PositionAssignment,
    PositionStatusSummary,
    normalize_assignment_type,
)
from .repository import ApiIncidentOrganizationRepository


DEFAULT_SPAN_OF_CONTROL_LIMIT = 7
MIN_FILLED_ASSIGNMENTS = 1
_LEGACY_SUPPORT_PREFIXES: tuple[tuple[str, str], ...] = (
    ("staff assistant", ASSIGNMENT_TYPE_STAFF_ASSISTANT),
    ("assistant", ASSIGNMENT_TYPE_ASSISTANT),
    ("deputy", ASSIGNMENT_TYPE_DEPUTY),
    ("trainee", ASSIGNMENT_TYPE_TRAINEE),
)


class IncidentOrganizationController:
    """Coordinates position structure, staffing, warnings, and form payloads."""

    def __init__(self, incident_id: str):
        self.incident_id = str(incident_id)
        self.repo = ApiIncidentOrganizationRepository(self.incident_id)
        self.personnel_repo = ApiPersonnelPoolRepository()

    # ------------------------------------------------------------------
    def add_position(self, values: dict[str, object]) -> int:
        """Create a position or organizational node from user-provided values."""

        position = OrganizationPosition(
            id=None,
            incident_id=self.incident_id,
            title=str(values.get("title", "")).strip(),
            classification=str(values.get("classification", "position")).strip() or "position",
            parent_position_id=self._optional_int(values.get("parent_position_id")),
            sort_order=int(values.get("sort_order", 0) or 0),
        )
        if not position.title:
            raise ValueError("Position title is required")
        return self.repo.upsert_position(position)

    def update_position(self, position_id: int, values: dict[str, object]) -> int:
        current = self.repo.get_position(position_id)
        if current is None:
            raise ValueError(f"Position {position_id} was not found")
        updated = OrganizationPosition(
            id=current.id,
            incident_id=self.incident_id,
            title=str(values.get("title", current.title)).strip(),
            classification=str(values.get("classification", current.classification)).strip()
            or current.classification,
            parent_position_id=self._optional_int(
                values.get("parent_position_id", current.parent_position_id)
            ),
            sort_order=int(values.get("sort_order", current.sort_order) or 0),
        )
        if not updated.title:
            raise ValueError("Position title is required")
        return self.repo.upsert_position(updated)

    def move_position(self, position_id: int, parent_position_id: int | None) -> None:
        self.repo.move_position(position_id, parent_position_id)

    def deactivate_position(self, position_id: int) -> None:
        self.repo.deactivate_position(position_id)

    def list_positions(self, include_inactive: bool = False) -> list[OrganizationPosition]:
        positions = self.repo.list_positions(include_inactive=include_inactive)
        visible_positions, _legacy_support_map = self._normalize_legacy_support_positions(positions)
        return visible_positions

    def get_position(self, position_id: int) -> OrganizationPosition | None:
        return self.repo.get_position(position_id)

    def list_operational_units(
        self, classifications: set[str] | None = None
    ) -> list[OrganizationPosition]:
        return self.repo.list_operational_units(classifications)

    def get_ops_section_id(self) -> int | None:
        """Return the position id of the Operations Section, or None if not found."""
        for pos in self.repo.list_positions():
            if pos.classification == "section" and "operations" in pos.title.lower():
                return pos.id
        return None

    def add_branch(
        self,
        name: str,
        parent_id: int | None,
        *,
        is_air_ops: bool = False,
    ) -> int:
        """Create a branch node and optionally assign a director under it.

        Air Operations is inferred from the branch title by downstream form
        builders until the dedicated handling is redesigned.
        """
        name = name.strip()
        if not name:
            raise ValueError("Branch name is required")
        branch_id = self.add_position({
            "title": name,
            "classification": "branch",
            "parent_position_id": parent_id,
        })
        return branch_id

    def add_division_group(
        self,
        name: str,
        classification: str,
        parent_id: int | None,
    ) -> int:
        """Create a division or group node and optionally assign a supervisor under it."""
        name = name.strip()
        if not name:
            raise ValueError("Division/Group name is required")
        if classification not in {"division", "group"}:
            raise ValueError("Classification must be 'division' or 'group'")
        unit_id = self.add_position({
            "title": name,
            "classification": classification,
            "parent_position_id": parent_id,
        })
        return unit_id

    # ------------------------------------------------------------------
    def list_templates(self) -> list[OrganizationTemplate]:
        return self.repo.list_templates()

    def apply_template(self, template_name: str) -> list[int]:
        template = self.repo.get_template_by_name(template_name)
        if template is None:
            raise ValueError(f"Organization template was not found: {template_name}")
        return self.repo.apply_template_payload(template.payload)

    # ------------------------------------------------------------------
    def assign_person(self, position_id: int, values: dict[str, object]) -> tuple[str, list[OrganizationWarning]]:
        """Assign personnel while preserving history and returning warnings.

        Qualification issues are intentionally non-blocking so AHJ-specific
        staffing decisions can proceed while still being visible to users.
        """

        if values.get("person_record") is None:
            raise ValueError("Select a personnel record before assigning to an organization position.")

        assignment = PositionAssignment(
            id=None,
            incident_id=self.incident_id,
            position_id=position_id,
            person_record=int(values["person_record"]),
            person_name=str(values.get("person_name") or "").strip(),
            assignment_type=normalize_assignment_type(values.get("assignment_type")),
            start_time=self._optional_text(values.get("start_time")),
            end_time=None,
        )
        position = self.repo.get_position(position_id)
        if position is None:
            raise ValueError(f"Position {position_id} was not found")
        if assignment.assignment_type == ASSIGNMENT_TYPE_PRIMARY:
            current_primary = [
                item for item in self.repo.list_assignments(position_id, active_only=True)
                if item.assignment_type == ASSIGNMENT_TYPE_PRIMARY
            ]
            if current_primary and not self._allows_multiple_primaries(position):
                raise ValueError(
                    "This position already has a primary assignee. "
                    "Multiple primary assignees are only allowed for Incident Commander."
                )
        assignment_id = self.repo.add_assignment(assignment)
        return assignment_id, self.qualification_warnings(position_id, assignment, position)

    def remove_assignment(
        self,
        assignment_id: str | int,
        *,
        changed_by: str | None = None,
        notes: str | None = None,
    ) -> None:
        self.repo.end_assignment(assignment_id, changed_by=changed_by, notes=notes)

    def list_assignments(
        self, position_id: int | None = None, *, active_only: bool = True
    ) -> list[PositionAssignment]:
        assignments = self.repo.list_assignments(position_id, active_only=active_only)
        positions = self.repo.list_positions()
        visible_positions, legacy_support_map = self._normalize_legacy_support_positions(positions)
        if not legacy_support_map:
            return assignments

        visible_position_ids = {position.id for position in visible_positions if position.id is not None}
        normalized: list[PositionAssignment] = []
        for assignment in assignments:
            remapped = legacy_support_map.get(assignment.position_id)
            if remapped is not None:
                parent_position_id, assignment_type = remapped
                normalized.append(
                    PositionAssignment(
                        id=assignment.id,
                        incident_id=assignment.incident_id,
                        position_id=parent_position_id,
                        person_record=assignment.person_record,
                        person_name=assignment.person_name,
                        assignment_type=assignment_type,
                        start_time=assignment.start_time,
                        end_time=assignment.end_time,
                        operational_period=assignment.operational_period,
                        assigned_by=assignment.assigned_by,
                        notes=assignment.notes,
                        created_at=assignment.created_at,
                        updated_at=assignment.updated_at,
                    )
                )
                continue
            if assignment.position_id in visible_position_ids:
                normalized.append(assignment)

        if position_id is not None:
            normalized = [assignment for assignment in normalized if assignment.position_id == position_id]
        return normalized

    def list_assignments_for_person(
        self, person_record: int, *, active_only: bool = True
    ) -> list[PositionAssignment]:
        return self.repo.list_assignments_for_person(person_record, active_only=active_only)

    # ------------------------------------------------------------------
    def staffing_summary(self) -> dict[int, PositionStatusSummary]:
        positions = self.list_positions()
        assignments = self.list_assignments(active_only=True)
        by_position: dict[int, list[PositionAssignment]] = defaultdict(list)
        for assignment in assignments:
            by_position[assignment.position_id].append(assignment)

        summary: dict[int, PositionStatusSummary] = {}
        for position in positions:
            current = by_position.get(position.id or 0, [])
            warnings = self.position_warnings(position, current, positions)
            if not current:
                status = "vacant"
            elif len(current) < MIN_FILLED_ASSIGNMENTS:
                status = "partially filled"
            elif (
                any(a.assignment_type == ASSIGNMENT_TYPE_TRAINEE for a in current)
                and len(current) == 1
            ):
                status = "partially filled"
            else:
                status = "filled"
            summary[position.id or 0] = PositionStatusSummary(
                position_id=position.id or 0,
                staffing_status=status,
                warnings=warnings,
            )
        return summary

    def position_warnings(
        self,
        position: OrganizationPosition,
        assignments: Iterable[PositionAssignment] | None = None,
        positions: Iterable[OrganizationPosition] | None = None,
    ) -> list[OrganizationWarning]:
        assignment_list = list(
            assignments if assignments is not None else self.list_assignments(position.id)
        )
        position_list = list(positions if positions is not None else self.list_positions())
        warnings: list[OrganizationWarning] = []
        child_count = sum(
            1 for item in position_list if item.parent_position_id == position.id
        )
        if child_count > DEFAULT_SPAN_OF_CONTROL_LIMIT:
            warnings.append(
                OrganizationWarning(
                    level="warning",
                    code="span_of_control",
                    message=(
                        f"{position.title} supervises {child_count} positions; "
                        f"recommended maximum is {DEFAULT_SPAN_OF_CONTROL_LIMIT}."
                    ),
                    position_id=position.id,
                )
            )
        for assignment in assignment_list:
            warnings.extend(
                self.qualification_warnings(position.id or 0, assignment, position)
            )
        return warnings

    def qualification_warnings(
        self,
        position_id: int,
        assignment: PositionAssignment,
        position: OrganizationPosition | None = None,
    ) -> list[OrganizationWarning]:
        position = position or self.repo.get_position(position_id)
        return []

    # ------------------------------------------------------------------
    def personnel_pool(self, query: str) -> list[dict[str, object | None]]:
        return self.personnel_repo.search_people(query)

    def build_ics203_payload(self, operational_period: str | None = None) -> dict[str, object]:
        """Return structured data ready for later ICS 203 rendering."""

        return self._build_generated_payload("ICS_203", operational_period)

    def build_ics207_payload(self, operational_period: str | None = None) -> dict[str, object]:
        """Return nodes and edges ready for later ICS 207 chart rendering."""

        payload = self._build_generated_payload("ICS_207", operational_period)
        positions = payload["positions"]
        payload["edges"] = [
            {"parent_position_id": item["parent_position_id"], "position_id": item["id"]}
            for item in positions
            if item["parent_position_id"] is not None
        ]
        return payload

    def _build_generated_payload(self, form_type: str, operational_period: str | None) -> dict[str, object]:
        positions = self.list_positions()
        assignments = self.list_assignments(active_only=True)
        assignments_by_position: dict[int, list[dict[str, object | None]]] = defaultdict(list)
        for assignment in assignments:
            assignments_by_position[assignment.position_id].append(
                {
                    "id": assignment.id,
                    "person_record": assignment.person_record,
                    "person_name": assignment.person_name,
                    "assignment_type": assignment.assignment_type,
                    "start_time": assignment.start_time,
                    "end_time": assignment.end_time,
                }
            )
        return {
            "form_type": form_type,
            "incident_id": self.incident_id,
            "operational_period": operational_period,
            "positions": [
                {
                    "id": position.id,
                    "title": position.title,
                    "classification": position.classification,
                    "parent_position_id": position.parent_position_id,
                    "assignments": assignments_by_position.get(position.id or 0, []),
                }
                for position in positions
            ],
        }

    @staticmethod
    def _optional_int(value: object) -> int | None:
        if value in (None, ""):
            return None
        return int(value)

    @staticmethod
    def _optional_text(value: object) -> str | None:
        if value in (None, ""):
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _qualification_list(value: object) -> list[str]:
        if value in (None, ""):
            return []
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        return [item.strip() for item in str(value).split(",") if item.strip()]

    @staticmethod
    def _allows_multiple_primaries(position: OrganizationPosition) -> bool:
        return (
            position.classification == "command"
            and position.title.strip().casefold() == "incident commander"
        )

    @staticmethod
    def _normalize_legacy_support_positions(
        positions: list[OrganizationPosition],
    ) -> tuple[list[OrganizationPosition], dict[int, tuple[int, str]]]:
        by_id = {position.id: position for position in positions if position.id is not None}
        legacy_support_map: dict[int, tuple[int, str]] = {}

        for position in positions:
            if position.id is None or position.parent_position_id is None:
                continue
            parent = by_id.get(position.parent_position_id)
            if parent is None:
                continue
            assignment_type = IncidentOrganizationController._legacy_support_assignment_type(
                position.title,
                parent.title,
            )
            if assignment_type is not None:
                legacy_support_map[position.id] = (parent.id, assignment_type)

        visible_positions = [
            position for position in positions if position.id not in legacy_support_map
        ]
        return visible_positions, legacy_support_map

    @staticmethod
    def _legacy_support_assignment_type(title: str, parent_title: str) -> str | None:
        normalized_title = title.strip().casefold()
        normalized_parent = parent_title.strip().casefold()
        for prefix, assignment_type in _LEGACY_SUPPORT_PREFIXES:
            expected = f"{prefix} {normalized_parent}"
            if normalized_title == expected:
                return assignment_type
        return None
