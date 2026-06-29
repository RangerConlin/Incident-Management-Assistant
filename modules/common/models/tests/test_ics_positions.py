from __future__ import annotations

from modules.common.models.ics_positions import (
    SUPPORT_ROLE_ASSISTANT,
    SUPPORT_ROLE_DEPUTY,
    SUPPORT_ROLE_STAFF_ASSISTANT,
    SUPPORT_ROLE_TRAINEE,
    all_position_names,
    get_position,
    position_names_by_group,
    positions_by_group,
)


def test_catalog_lookup_supports_key_title_and_alias() -> None:
    by_key = get_position("operations_section_chief")
    by_title = get_position("Operations Section Chief")
    by_alias = get_position("OSC")

    assert by_key is not None
    assert by_key == by_title == by_alias
    assert {
        SUPPORT_ROLE_DEPUTY,
        SUPPORT_ROLE_ASSISTANT,
        SUPPORT_ROLE_STAFF_ASSISTANT,
        SUPPORT_ROLE_TRAINEE,
    } <= set(by_key.default_support_roles)


def test_group_helpers_return_canonical_titles() -> None:
    grouped = position_names_by_group()
    detailed = positions_by_group()

    assert "Operations Section Chief" in grouped["Operations Section"]
    assert any(position.title == "Safety Officer" for position in detailed["Command Staff"])
    assert "Finance/Administration Section Chief" in all_position_names()
    assert "Deputy Incident Commander" not in all_position_names()


def test_every_position_allows_staff_assistant_and_can_override_scope() -> None:
    for title in all_position_names():
        position = get_position(title)
        assert position is not None
        assert position.allows_support_role(SUPPORT_ROLE_STAFF_ASSISTANT)

    ic = get_position("incident_commander")
    assert ic is not None
    assert ic.permission_scope_for_role(SUPPORT_ROLE_STAFF_ASSISTANT) == "incident.command.staff"
    assert ic.permission_scope_for_role(SUPPORT_ROLE_DEPUTY) == "incident.command"
