from __future__ import annotations

"""Controller for incident organization management."""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable

from .personnel_repo import ApiPersonnelPoolRepository
from .models import (
    GeneratedFormSnapshot,
    OrganizationPosition,
    OrganizationTemplate,
    OrganizationWarning,
    PositionAssignment,
    PositionStatusSummary,
)
from .repository import ApiIncidentOrganizationRepository, IncidentOrganizationRepository


DEFAULT_SPAN_OF_CONTROL_LIMIT = 7
MIN_FILLED_ASSIGNMENTS = 1


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
            operational_period=self._optional_text(values.get("operational_period")),
            required_qualifications=self._qualification_list(values.get("required_qualifications")),
            is_critical=bool(values.get("is_critical", False)),
            is_custom=bool(values.get("is_custom", False)),
            status=str(values.get("status", "active") or "active"),
            sort_order=int(values.get("sort_order", 0) or 0),
            notes=self._optional_text(values.get("notes")),
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
            operational_period=self._optional_text(
                values.get("operational_period", current.operational_period)
            ),
            required_qualifications=self._qualification_list(
                values.get("required_qualifications", current.required_qualifications)
            ),
            is_critical=bool(values.get("is_critical", current.is_critical)),
            is_custom=bool(values.get("is_custom", current.is_custom)),
            status=str(values.get("status", current.status) or current.status),
            sort_order=int(values.get("sort_order", current.sort_order) or 0),
            notes=self._optional_text(values.get("notes", current.notes)),
        )
        if not updated.title:
            raise ValueError("Position title is required")
        return self.repo.upsert_position(updated)

    def move_position(self, position_id: int, parent_position_id: int | None) -> None:
        self.repo.move_position(position_id, parent_position_id)

    def deactivate_position(self, position_id: int) -> None:
        self.repo.deactivate_position(position_id)

    def list_positions(self, include_inactive: bool = False) -> list[OrganizationPosition]:
        return self.repo.list_positions(include_inactive=include_inactive)

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
        director_name: str | None = None,
        notes: str | None = None,
    ) -> int:
        """Create a branch node and optionally assign a director under it."""
        name = name.strip()
        if not name:
            raise ValueError("Branch name is required")
        branch_id = self.add_position({
            "title": name,
            "classification": "branch",
            "parent_position_id": parent_id,
            "is_custom": True,
            "notes": notes,
        })
        if director_name and director_name.strip():
            director_pos_id = self.add_position({
                "title": "Branch Director",
                "classification": "position",
                "parent_position_id": branch_id,
                "is_custom": True,
                "sort_order": 0,
            })
            self.assign_person(director_pos_id, {
                "display_name": director_name.strip(),
                "assignment_type": "primary",
            })
        return branch_id

    def add_division_group(
        self,
        name: str,
        classification: str,
        parent_id: int | None,
        *,
        supervisor_name: str | None = None,
        notes: str | None = None,
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
            "is_custom": True,
            "notes": notes,
        })
        if supervisor_name and supervisor_name.strip():
            supervisor_title = (
                "Division Supervisor" if classification == "division" else "Group Supervisor"
            )
            sup_pos_id = self.add_position({
                "title": supervisor_title,
                "classification": "position",
                "parent_position_id": unit_id,
                "is_custom": True,
                "sort_order": 0,
            })
            self.assign_person(sup_pos_id, {
                "display_name": supervisor_name.strip(),
                "assignment_type": "primary",
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
    def assign_person(self, position_id: int, values: dict[str, object]) -> tuple[int, list[OrganizationWarning]]:
        """Assign personnel while preserving history and returning warnings.

        Qualification issues are intentionally non-blocking so AHJ-specific
        staffing decisions can proceed while still being visible to users.
        """

        assignment = PositionAssignment(
            id=None,
            incident_id=self.incident_id,
            position_id=position_id,
            personnel_id=self._optional_text(values.get("personnel_id")),
            display_name=str(values.get("display_name", "")).strip(),
            assignment_type=str(values.get("assignment_type", "primary") or "primary"),
            start_time=self._optional_text(values.get("start_time")),
            end_time=None,
            operational_period=self._optional_text(values.get("operational_period")),
            assigned_by=self._optional_text(values.get("assigned_by")),
            notes=self._optional_text(values.get("notes")),
        )
        if not assignment.display_name:
            raise ValueError("Assigned personnel name is required")
        assignment_id = self.repo.add_assignment(assignment)
        return assignment_id, self.qualification_warnings(position_id, assignment)

    def remove_assignment(
        self,
        assignment_id: int,
        *,
        changed_by: str | None = None,
        notes: str | None = None,
    ) -> None:
        self.repo.end_assignment(assignment_id, changed_by=changed_by, notes=notes)

    def list_assignments(
        self, position_id: int | None = None, *, active_only: bool = True
    ) -> list[PositionAssignment]:
        return self.repo.list_assignments(position_id, active_only=active_only)

    def list_assignment_history(self, position_id: int | None = None):
        return self.repo.list_assignment_history(position_id)

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
                any(a.assignment_type == "trainee" for a in current)
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
        if position.is_critical and not assignment_list:
            warnings.append(
                OrganizationWarning(
                    level="warning",
                    code="critical_vacancy",
                    message=f"Critical position is vacant: {position.title}",
                    position_id=position.id,
                )
            )
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
        if position is None or not position.required_qualifications:
            return []
        # The current personnel catalog has inconsistent qualification storage.
        # Until a common qualifications table is available, assignments are
        # allowed and flagged for review instead of blocked.
        return [
            OrganizationWarning(
                level="warning",
                code="qualification_review",
                message=(
                    f"Review qualifications for {assignment.display_name}: "
                    f"{', '.join(position.required_qualifications)} required."
                ),
                position_id=position_id,
            )
        ]

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

    def save_generated_snapshot(self, form_type: str, payload: dict[str, object]) -> int:
        snapshot = GeneratedFormSnapshot(
            id=None,
            incident_id=self.incident_id,
            form_type=form_type,
            generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            operational_period=payload.get("operational_period"),
            source_version=None,
            payload=payload,
        )
        return self.repo.save_generated_snapshot(snapshot)

    def _build_generated_payload(self, form_type: str, operational_period: str | None) -> dict[str, object]:
        positions = self.list_positions()
        if operational_period:
            positions = [
                item
                for item in positions
                if item.operational_period in (None, "", operational_period)
            ]
        assignments = self.list_assignments(active_only=True)
        assignments_by_position: dict[int, list[dict[str, object | None]]] = defaultdict(list)
        for assignment in assignments:
            assignments_by_position[assignment.position_id].append(
                {
                    "id": assignment.id,
                    "personnel_id": assignment.personnel_id,
                    "display_name": assignment.display_name,
                    "assignment_type": assignment.assignment_type,
                    "start_time": assignment.start_time,
                    "end_time": assignment.end_time,
                    "operational_period": assignment.operational_period,
                    "notes": assignment.notes,
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
                    "required_qualifications": position.required_qualifications,
                    "is_critical": position.is_critical,
                    "is_custom": position.is_custom,
                    "status": position.status,
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
