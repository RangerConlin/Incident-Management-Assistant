"""Pure-logic tests for Stage 6 team readiness validation and conflict
detection -- no MongoDB required."""
from __future__ import annotations

from sarapp_db.services.team_validation import (
    NOT_EVALUATED,
    NOT_READY,
    READY,
    READY_WITH_LIMITATIONS,
    RequirementSpec,
    TeamComposition,
    evaluate_team,
    find_conflicting_assignments,
)


def test_not_evaluated_when_no_resource_type_linked():
    result = evaluate_team(None, TeamComposition(personnel_ids=[1, 2, 3, 4]))
    assert result.outcome == NOT_EVALUATED


def test_ready_when_all_requirements_met():
    requirements = RequirementSpec(min_personnel=2, required_qualifications=["Ground Team Member"])
    composition = TeamComposition(
        personnel_ids=[1, 2],
        personnel_qualifications={1: {"Ground Team Member"}, 2: {"Team Leader"}},
    )
    result = evaluate_team(requirements, composition)
    assert result.outcome == READY


def test_not_ready_when_understaffed():
    requirements = RequirementSpec(min_personnel=4)
    composition = TeamComposition(personnel_ids=[1, 2])
    result = evaluate_team(requirements, composition)
    assert result.outcome == NOT_READY
    assert "2 additional personnel" in result.messages[0]


def test_ready_with_limitations_when_qualification_missing_but_staffed():
    """Matches the spec's example message exactly: 'Requires one
    additional qualified Ground Team Member.'"""
    requirements = RequirementSpec(min_personnel=1, required_qualifications=["Ground Team Member"])
    composition = TeamComposition(personnel_ids=[1], personnel_qualifications={1: {"Driver"}})
    result = evaluate_team(requirements, composition)
    assert result.outcome == READY_WITH_LIMITATIONS
    assert "Requires one additional qualified Ground Team Member." in result.messages


def test_not_ready_when_required_equipment_type_missing():
    requirements = RequirementSpec(min_personnel=1, required_equipment_type_ids=[500])
    composition = TeamComposition(personnel_ids=[1], assigned_resource_type_ids=[])
    result = evaluate_team(requirements, composition)
    assert result.outcome == NOT_READY


def test_conflict_forces_not_ready_even_if_otherwise_fully_staffed():
    requirements = RequirementSpec(min_personnel=1)
    composition = TeamComposition(personnel_ids=[1], conflicts=["Vehicle 9 is already committed to team GT-2."])
    result = evaluate_team(requirements, composition)
    assert result.outcome == NOT_READY
    assert result.messages == ["Vehicle 9 is already committed to team GT-2."]


def test_qualification_match_is_case_insensitive():
    requirements = RequirementSpec(required_qualifications=["ground team member"])
    composition = TeamComposition(personnel_ids=[1], personnel_qualifications={1: {"Ground Team Member"}})
    result = evaluate_team(requirements, composition)
    assert result.outcome == READY


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

def test_find_conflicting_assignments_detects_shared_vehicle():
    other_teams = [
        {"team_id": 2, "team_name": "GT-2", "disbanded": False, "refs": [("vehicle", 9), ("personnel", 5)]},
    ]
    conflicts = find_conflicting_assignments(1, [("vehicle", 9)], other_teams)
    assert len(conflicts) == 1
    assert "Vehicle 9" in conflicts[0] and "GT-2" in conflicts[0]


def test_find_conflicting_assignments_ignores_disbanded_teams():
    other_teams = [{"team_id": 2, "team_name": "GT-2", "disbanded": True, "refs": [("vehicle", 9)]}]
    conflicts = find_conflicting_assignments(1, [("vehicle", 9)], other_teams)
    assert conflicts == []


def test_find_conflicting_assignments_ignores_self():
    other_teams = [{"team_id": 1, "team_name": "GT-1", "disbanded": False, "refs": [("vehicle", 9)]}]
    conflicts = find_conflicting_assignments(1, [("vehicle", 9)], other_teams)
    assert conflicts == []


def test_find_conflicting_assignments_no_overlap_means_no_conflict():
    other_teams = [{"team_id": 2, "team_name": "GT-2", "disbanded": False, "refs": [("vehicle", 10)]}]
    conflicts = find_conflicting_assignments(1, [("vehicle", 9)], other_teams)
    assert conflicts == []
