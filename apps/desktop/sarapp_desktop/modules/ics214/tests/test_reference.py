"""Coverage for immutable ICS reference identities."""

from sarapp_db.ics_reference import (
    BUILTIN_LOGS,
    ORGANIZATIONAL_ELEMENT_TYPES,
    REFERENCE_POSITIONS,
)


def test_reference_keys_are_unique_and_include_standard_logs():
    keys = [definition["key"] for definition in BUILTIN_LOGS]

    assert len(keys) == len(set(keys))
    assert "medical_unit" in keys
    assert "operations_section" in keys
    assert "position:medical_unit_leader" in keys
    assert "position:incident_commander" in keys


def test_repeatable_organization_types_are_reference_types_not_single_instances():
    element_types = dict(ORGANIZATIONAL_ELEMENT_TYPES)
    position_keys = dict(REFERENCE_POSITIONS)

    assert element_types["branch"] == "Branch"
    assert element_types["division"] == "Division"
    assert element_types["strike_team"] == "Strike Team"
    assert "division" not in position_keys
