from __future__ import annotations

from types import SimpleNamespace

import pytest

from modules.command.incident_organization.controller import IncidentOrganizationController
from modules.command.incident_organization.models import (
    ASSIGNMENT_TYPE_ASSISTANT,
    ASSIGNMENT_TYPE_DEPUTY,
    ASSIGNMENT_TYPE_PRIMARY,
    ASSIGNMENT_TYPE_STAFF_ASSISTANT,
    OrganizationPosition,
    PositionAssignment,
    normalize_assignment_type,
)
from modules.command.incident_organization.repository import ApiIncidentOrganizationRepository


def test_normalize_assignment_type_keeps_assistant_distinct() -> None:
    assert normalize_assignment_type("assistant") == ASSIGNMENT_TYPE_ASSISTANT
    assert normalize_assignment_type("staff_assistant") == ASSIGNMENT_TYPE_STAFF_ASSISTANT
    assert normalize_assignment_type("staff assistant") == ASSIGNMENT_TYPE_STAFF_ASSISTANT
    assert normalize_assignment_type("unknown") == ASSIGNMENT_TYPE_PRIMARY


def test_assignment_docs_return_normalized_role() -> None:
    assignment = ApiIncidentOrganizationRepository._doc_to_assignment(
        {
            "assignment_id": 12,
            "incident_id": "TEST-123",
            "position_id": 7,
            "display_name": "Jordan Planner",
            "assignment_type": "assistant",
        }
    )

    assert assignment.assignment_type == ASSIGNMENT_TYPE_ASSISTANT


def test_second_primary_allowed_for_incident_commander() -> None:
    controller = IncidentOrganizationController.__new__(IncidentOrganizationController)
    controller.incident_id = "TEST-123"
    position = OrganizationPosition(
        id=5,
        incident_id="TEST-123",
        title="Incident Commander",
        classification="command",
    )
    existing_primary = PositionAssignment(
        id=10,
        incident_id="TEST-123",
        position_id=5,
        personnel_id="1",
        display_name="Alex IC",
        assignment_type=ASSIGNMENT_TYPE_PRIMARY,
    )
    controller.repo = SimpleNamespace(
        get_position=lambda _position_id: position,
        list_assignments=lambda _position_id, active_only=True: [existing_primary],
        add_assignment=lambda _assignment: 99,
    )
    controller.qualification_warnings = lambda *_args, **_kwargs: []

    assignment_id, warnings = controller.assign_person(
        5,
        {"display_name": "Jordan IC", "assignment_type": "primary"},
    )

    assert assignment_id == 99
    assert warnings == []


def test_second_primary_rejected_for_other_command_positions() -> None:
    controller = IncidentOrganizationController.__new__(IncidentOrganizationController)
    controller.incident_id = "TEST-123"
    position = OrganizationPosition(
        id=6,
        incident_id="TEST-123",
        title="Operations Section Chief",
        classification="command",
    )
    existing_primary = PositionAssignment(
        id=10,
        incident_id="TEST-123",
        position_id=6,
        personnel_id="1",
        display_name="Alex OSC",
        assignment_type=ASSIGNMENT_TYPE_PRIMARY,
    )
    controller.repo = SimpleNamespace(
        get_position=lambda _position_id: position,
        list_assignments=lambda _position_id, active_only=True: [existing_primary],
        add_assignment=lambda _assignment: 99,
    )

    with pytest.raises(ValueError, match="only allowed for Incident Commander"):
        controller.assign_person(5, {"display_name": "Jordan IC", "assignment_type": "primary"})


def test_list_positions_hides_legacy_deputy_nodes() -> None:
    controller = IncidentOrganizationController.__new__(IncidentOrganizationController)
    controller.incident_id = "TEST-123"
    parent = OrganizationPosition(
        id=5,
        incident_id="TEST-123",
        title="Operations Section Chief",
        classification="section",
    )
    legacy_deputy = OrganizationPosition(
        id=6,
        incident_id="TEST-123",
        title="Deputy Operations Section Chief",
        classification="position",
        parent_position_id=5,
    )
    controller.repo = SimpleNamespace(
        list_positions=lambda include_inactive=False: [parent, legacy_deputy],
    )

    positions = controller.list_positions()

    assert [position.title for position in positions] == ["Operations Section Chief"]


def test_list_assignments_remaps_legacy_deputy_nodes_to_parent_position() -> None:
    controller = IncidentOrganizationController.__new__(IncidentOrganizationController)
    controller.incident_id = "TEST-123"
    parent = OrganizationPosition(
        id=5,
        incident_id="TEST-123",
        title="Operations Section Chief",
        classification="section",
    )
    legacy_deputy = OrganizationPosition(
        id=6,
        incident_id="TEST-123",
        title="Deputy Operations Section Chief",
        classification="position",
        parent_position_id=5,
    )
    deputy_assignment = PositionAssignment(
        id=10,
        incident_id="TEST-123",
        position_id=6,
        personnel_id="1",
        display_name="Jordan Deputy",
        assignment_type=ASSIGNMENT_TYPE_PRIMARY,
    )
    controller.repo = SimpleNamespace(
        list_positions=lambda include_inactive=False: [parent, legacy_deputy],
        list_assignments=lambda position_id=None, active_only=True: [deputy_assignment],
    )

    assignments = controller.list_assignments(5)

    assert len(assignments) == 1
    assert assignments[0].position_id == 5
    assert assignments[0].assignment_type == ASSIGNMENT_TYPE_DEPUTY
    assert assignments[0].display_name == "Jordan Deputy"
