"""Canonical ICS position catalog used across the application.

This module provides a stable, code-defined catalog of standard ICS positions
that can be reused by organization builders, permissions, routing, meetings,
and other position-aware features. The catalog is intentionally broader than a
single incident's live organization chart.
"""

from __future__ import annotations

from dataclasses import dataclass, field


SUPPORT_ROLE_PRIMARY = "primary"
SUPPORT_ROLE_DEPUTY = "deputy"
SUPPORT_ROLE_ASSISTANT = "assistant"
SUPPORT_ROLE_STAFF_ASSISTANT = "staff_assistant"
SUPPORT_ROLE_TRAINEE = "trainee"
SUPPORT_ROLE_RELIEF = "relief"


@dataclass(slots=True, frozen=True)
class IcsPosition:
    """A single canonical position entry in the ICS position catalog."""

    key: str
    title: str
    group: str
    section: str
    kind: str
    parent_key: str | None = None
    aliases: tuple[str, ...] = ()
    default_support_roles: tuple[str, ...] = field(default_factory=tuple)
    permission_scope: str | None = None
    subtype_permission_scopes: dict[str, str] = field(default_factory=dict)

    @property
    def name(self) -> str:
        """Backward-compatible alias for older callers."""
        return self.title

    def allows_support_role(self, role: str) -> bool:
        """Return True when the position allows the given support role."""

        return role == SUPPORT_ROLE_PRIMARY or role in self.default_support_roles

    def permission_scope_for_role(self, role: str) -> str | None:
        """Return the effective permission scope for a role on this position.

        Most support roles inherit the parent/base position scope. Callers can
        later define narrower subtype scopes for support roles that should not
        receive full parent privileges.
        """

        return self.subtype_permission_scopes.get(role, self.permission_scope)


def _support_roles(
    *roles: str,
    include_staff_assistant: bool = True,
) -> tuple[str, ...]:
    """Build a deduplicated support-role tuple for catalog entries."""

    ordered: list[str] = []
    if include_staff_assistant:
        ordered.append(SUPPORT_ROLE_STAFF_ASSISTANT)
    ordered.extend(roles)
    seen: set[str] = set()
    result: list[str] = []
    for role in ordered:
        if role and role not in seen:
            seen.add(role)
            result.append(role)
    return tuple(result)


ICS_POSITIONS: list[IcsPosition] = [
    IcsPosition(
        key="incident_commander",
        title="Incident Commander",
        group="Command Staff",
        section="Command",
        kind="command",
        default_support_roles=_support_roles(
            SUPPORT_ROLE_DEPUTY,
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.command",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.command.staff",
        },
    ),
    IcsPosition(
        key="safety_officer",
        title="Safety Officer",
        group="Command Staff",
        section="Command",
        kind="position",
        parent_key="incident_commander",
        default_support_roles=_support_roles(
            SUPPORT_ROLE_ASSISTANT,
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.safety",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.safety.staff",
        },
    ),
    IcsPosition(
        key="public_information_officer",
        title="Public Information Officer",
        group="Command Staff",
        section="Command",
        kind="position",
        parent_key="incident_commander",
        aliases=("PIO",),
        default_support_roles=_support_roles(
            SUPPORT_ROLE_ASSISTANT,
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.public_information",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.public_information.staff",
        },
    ),
    IcsPosition(
        key="liaison_officer",
        title="Liaison Officer",
        group="Command Staff",
        section="Command",
        kind="position",
        parent_key="incident_commander",
        aliases=("LOFR",),
        default_support_roles=_support_roles(
            SUPPORT_ROLE_ASSISTANT,
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.liaison",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.liaison.staff",
        },
    ),
    IcsPosition(
        key="operations_section_chief",
        title="Operations Section Chief",
        group="Operations Section",
        section="Operations",
        kind="section",
        parent_key="incident_commander",
        aliases=("OSC",),
        default_support_roles=_support_roles(
            SUPPORT_ROLE_DEPUTY,
            SUPPORT_ROLE_ASSISTANT,
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.operations",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.operations.staff",
        },
    ),
    IcsPosition(
        key="staging_area_manager",
        title="Staging Area Manager",
        group="Operations Section",
        section="Operations",
        kind="position",
        parent_key="operations_section_chief",
        default_support_roles=_support_roles(
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.operations.staging",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.operations.staging.staff",
        },
    ),
    IcsPosition(
        key="air_operations_branch_director",
        title="Air Operations Branch Director",
        group="Operations Section",
        section="Operations",
        kind="branch",
        parent_key="operations_section_chief",
        aliases=("AOBD",),
        default_support_roles=_support_roles(
            SUPPORT_ROLE_DEPUTY,
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.operations.air",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.operations.air.staff",
        },
    ),
    IcsPosition(
        key="ground_operations_branch_director",
        title="Ground Operations Branch Director",
        group="Operations Section",
        section="Operations",
        kind="branch",
        parent_key="operations_section_chief",
        default_support_roles=_support_roles(
            SUPPORT_ROLE_DEPUTY,
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.operations.ground",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.operations.ground.staff",
        },
    ),
    IcsPosition(
        key="branch_director",
        title="Branch Director",
        group="Operations Section",
        section="Operations",
        kind="branch",
        parent_key="operations_section_chief",
        default_support_roles=_support_roles(
            SUPPORT_ROLE_DEPUTY,
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.operations.branch",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.operations.branch.staff",
        },
    ),
    IcsPosition(
        key="division_group_supervisor",
        title="Division/Group Supervisor",
        group="Operations Section",
        section="Operations",
        kind="unit",
        parent_key="branch_director",
        default_support_roles=_support_roles(
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.operations.division_group",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.operations.division_group.staff",
        },
    ),
    IcsPosition(
        key="helibase_manager",
        title="Helibase Manager",
        group="Operations Section",
        section="Operations",
        kind="position",
        parent_key="air_operations_branch_director",
        default_support_roles=_support_roles(
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.operations.air",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.operations.air.staff",
        },
    ),
    IcsPosition(
        key="air_support_group_supervisor",
        title="Air Support Group Supervisor",
        group="Operations Section",
        section="Operations",
        kind="position",
        parent_key="air_operations_branch_director",
        default_support_roles=_support_roles(
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.operations.air",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.operations.air.staff",
        },
    ),
    IcsPosition(
        key="operations_supervisor",
        title="Operations Supervisor",
        group="Operations Section",
        section="Operations",
        kind="position",
        parent_key="operations_section_chief",
        default_support_roles=_support_roles(
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.operations",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.operations.staff",
        },
    ),
    IcsPosition(
        key="planning_section_chief",
        title="Planning Section Chief",
        group="Planning Section",
        section="Planning",
        kind="section",
        parent_key="incident_commander",
        aliases=("PSC",),
        default_support_roles=_support_roles(
            SUPPORT_ROLE_DEPUTY,
            SUPPORT_ROLE_ASSISTANT,
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.planning",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.planning.staff",
        },
    ),
    IcsPosition(
        key="resources_unit_leader",
        title="Resources Unit Leader",
        group="Planning Section",
        section="Planning",
        kind="position",
        parent_key="planning_section_chief",
        aliases=("RESL",),
        default_support_roles=_support_roles(
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.planning.resources",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.planning.resources.staff",
        },
    ),
    IcsPosition(
        key="situation_unit_leader",
        title="Situation Unit Leader",
        group="Planning Section",
        section="Planning",
        kind="position",
        parent_key="planning_section_chief",
        aliases=("SITL",),
        default_support_roles=_support_roles(
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.planning.situation",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.planning.situation.staff",
        },
    ),
    IcsPosition(
        key="documentation_unit_leader",
        title="Documentation Unit Leader",
        group="Planning Section",
        section="Planning",
        kind="position",
        parent_key="planning_section_chief",
        aliases=("DOCL",),
        default_support_roles=_support_roles(
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.planning.documentation",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.planning.documentation.staff",
        },
    ),
    IcsPosition(
        key="demobilization_unit_leader",
        title="Demobilization Unit Leader",
        group="Planning Section",
        section="Planning",
        kind="position",
        parent_key="planning_section_chief",
        aliases=("DMOB",),
        default_support_roles=_support_roles(
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.planning.demob",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.planning.demob.staff",
        },
    ),
    IcsPosition(
        key="logistics_section_chief",
        title="Logistics Section Chief",
        group="Logistics Section",
        section="Logistics",
        kind="section",
        parent_key="incident_commander",
        aliases=("LSC",),
        default_support_roles=_support_roles(
            SUPPORT_ROLE_DEPUTY,
            SUPPORT_ROLE_ASSISTANT,
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.logistics",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.logistics.staff",
        },
    ),
    IcsPosition(
        key="service_branch_director",
        title="Service Branch Director",
        group="Logistics Section",
        section="Logistics",
        kind="branch",
        parent_key="logistics_section_chief",
        default_support_roles=_support_roles(
            SUPPORT_ROLE_DEPUTY,
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.logistics.service_branch",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.logistics.service_branch.staff",
        },
    ),
    IcsPosition(
        key="support_branch_director",
        title="Support Branch Director",
        group="Logistics Section",
        section="Logistics",
        kind="branch",
        parent_key="logistics_section_chief",
        default_support_roles=_support_roles(
            SUPPORT_ROLE_DEPUTY,
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.logistics.support_branch",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.logistics.support_branch.staff",
        },
    ),
    IcsPosition(
        key="communications_unit_leader",
        title="Communications Unit Leader",
        group="Logistics Section",
        section="Logistics",
        kind="position",
        parent_key="service_branch_director",
        aliases=("COML",),
        default_support_roles=_support_roles(
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.logistics.communications",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.logistics.communications.staff",
        },
    ),
    IcsPosition(
        key="medical_unit_leader",
        title="Medical Unit Leader",
        group="Logistics Section",
        section="Logistics",
        kind="position",
        parent_key="service_branch_director",
        default_support_roles=_support_roles(
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.logistics.medical",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.logistics.medical.staff",
        },
    ),
    IcsPosition(
        key="food_unit_leader",
        title="Food Unit Leader",
        group="Logistics Section",
        section="Logistics",
        kind="position",
        parent_key="service_branch_director",
        default_support_roles=_support_roles(
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.logistics.food",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.logistics.food.staff",
        },
    ),
    IcsPosition(
        key="supply_unit_leader",
        title="Supply Unit Leader",
        group="Logistics Section",
        section="Logistics",
        kind="position",
        parent_key="support_branch_director",
        default_support_roles=_support_roles(
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.logistics.supply",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.logistics.supply.staff",
        },
    ),
    IcsPosition(
        key="facilities_unit_leader",
        title="Facilities Unit Leader",
        group="Logistics Section",
        section="Logistics",
        kind="position",
        parent_key="support_branch_director",
        default_support_roles=_support_roles(
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.logistics.facilities",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.logistics.facilities.staff",
        },
    ),
    IcsPosition(
        key="ground_support_unit_leader",
        title="Ground Support Unit Leader",
        group="Logistics Section",
        section="Logistics",
        kind="position",
        parent_key="support_branch_director",
        default_support_roles=_support_roles(
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.logistics.ground_support",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.logistics.ground_support.staff",
        },
    ),
    IcsPosition(
        key="finance_admin_section_chief",
        title="Finance/Administration Section Chief",
        group="Finance/Admin Section",
        section="Finance/Admin",
        kind="section",
        parent_key="incident_commander",
        aliases=("FSC",),
        default_support_roles=_support_roles(
            SUPPORT_ROLE_DEPUTY,
            SUPPORT_ROLE_ASSISTANT,
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.finance_admin",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.finance_admin.staff",
        },
    ),
    IcsPosition(
        key="time_unit_leader",
        title="Time Unit Leader",
        group="Finance/Admin Section",
        section="Finance/Admin",
        kind="position",
        parent_key="finance_admin_section_chief",
        default_support_roles=_support_roles(
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.finance_admin.time",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.finance_admin.time.staff",
        },
    ),
    IcsPosition(
        key="procurement_unit_leader",
        title="Procurement Unit Leader",
        group="Finance/Admin Section",
        section="Finance/Admin",
        kind="position",
        parent_key="finance_admin_section_chief",
        default_support_roles=_support_roles(
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.finance_admin.procurement",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.finance_admin.procurement.staff",
        },
    ),
    IcsPosition(
        key="compensation_claims_unit_leader",
        title="Compensation/Claims Unit Leader",
        group="Finance/Admin Section",
        section="Finance/Admin",
        kind="position",
        parent_key="finance_admin_section_chief",
        default_support_roles=_support_roles(
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.finance_admin.comp_claims",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.finance_admin.comp_claims.staff",
        },
    ),
    IcsPosition(
        key="cost_unit_leader",
        title="Cost Unit Leader",
        group="Finance/Admin Section",
        section="Finance/Admin",
        kind="position",
        parent_key="finance_admin_section_chief",
        default_support_roles=_support_roles(
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.finance_admin.cost",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.finance_admin.cost.staff",
        },
    ),
    IcsPosition(
        key="intelligence_section_chief",
        title="Intelligence Section Chief",
        group="Intelligence/Investigations Section",
        section="Intelligence/Investigations",
        kind="section",
        parent_key="incident_commander",
        aliases=("ISC",),
        default_support_roles=_support_roles(
            SUPPORT_ROLE_DEPUTY,
            SUPPORT_ROLE_ASSISTANT,
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.intelligence",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.intelligence.staff",
        },
    ),
    IcsPosition(
        key="intel_investigations_supervisor",
        title="Intel/Investigations Supervisor",
        group="Intelligence/Investigations Section",
        section="Intelligence/Investigations",
        kind="position",
        parent_key="intelligence_section_chief",
        default_support_roles=_support_roles(
            SUPPORT_ROLE_TRAINEE,
            SUPPORT_ROLE_RELIEF,
        ),
        permission_scope="incident.intelligence",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.intelligence.staff",
        },
    ),
    IcsPosition(
        key="agency_representative",
        title="Agency Representative",
        group="Additional ICS Roles",
        section="Additional Roles",
        kind="position",
        aliases=("AREP",),
        permission_scope="incident.agency_rep",
        default_support_roles=_support_roles(),
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.agency_rep.staff",
        },
    ),
    IcsPosition(
        key="technical_specialist",
        title="Technical Specialist",
        group="Additional ICS Roles",
        section="Additional Roles",
        kind="position",
        default_support_roles=_support_roles(),
        permission_scope="incident.specialist",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.specialist.staff",
        },
    ),
    IcsPosition(
        key="subject_matter_expert",
        title="Subject Matter Expert",
        group="Additional ICS Roles",
        section="Additional Roles",
        kind="position",
        aliases=("SME",),
        default_support_roles=_support_roles(),
        permission_scope="incident.specialist",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.specialist.staff",
        },
    ),
    IcsPosition(
        key="command_staff_generic",
        title="Command Staff (Generic)",
        group="Additional ICS Roles",
        section="Additional Roles",
        kind="position",
        default_support_roles=_support_roles(),
        permission_scope="incident.command",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.command.staff",
        },
    ),
    IcsPosition(
        key="general_staff_generic",
        title="General Staff (Generic)",
        group="Additional ICS Roles",
        section="Additional Roles",
        kind="position",
        default_support_roles=_support_roles(),
        permission_scope="incident.general_staff",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.general_staff.staff",
        },
    ),
    IcsPosition(
        key="section_chief_generic",
        title="Section Chief (Generic)",
        group="Additional ICS Roles",
        section="Additional Roles",
        kind="position",
        default_support_roles=_support_roles(),
        permission_scope="incident.section_chief",
        subtype_permission_scopes={
            SUPPORT_ROLE_STAFF_ASSISTANT: "incident.section_chief.staff",
        },
    ),
]


ICS_POSITIONS_BY_KEY: dict[str, IcsPosition] = {position.key: position for position in ICS_POSITIONS}
ICS_POSITIONS_BY_TITLE: dict[str, IcsPosition] = {
    position.title.casefold(): position for position in ICS_POSITIONS
}
ICS_POSITIONS_BY_ALIAS: dict[str, IcsPosition] = {
    alias.casefold(): position
    for position in ICS_POSITIONS
    for alias in position.aliases
}


def get_position(key_or_title: str) -> IcsPosition | None:
    """Return a canonical position by key, title, or alias."""

    lookup = key_or_title.strip()
    if not lookup:
        return None
    return (
        ICS_POSITIONS_BY_KEY.get(lookup)
        or ICS_POSITIONS_BY_TITLE.get(lookup.casefold())
        or ICS_POSITIONS_BY_ALIAS.get(lookup.casefold())
    )


def positions_by_group() -> dict[str, list[IcsPosition]]:
    """Return canonical positions grouped by UI section label."""

    groups: dict[str, list[IcsPosition]] = {}
    for position in ICS_POSITIONS:
        groups.setdefault(position.group, []).append(position)
    return groups


def position_names_by_group() -> dict[str, list[str]]:
    """Return positions grouped by their section label."""

    return {
        group: [position.title for position in positions]
        for group, positions in positions_by_group().items()
    }


def all_position_names() -> list[str]:
    """Return every canonical position title in the catalog."""

    return [position.title for position in ICS_POSITIONS]


__all__ = [
    "ICS_POSITIONS",
    "ICS_POSITIONS_BY_ALIAS",
    "ICS_POSITIONS_BY_KEY",
    "ICS_POSITIONS_BY_TITLE",
    "IcsPosition",
    "SUPPORT_ROLE_ASSISTANT",
    "SUPPORT_ROLE_DEPUTY",
    "SUPPORT_ROLE_PRIMARY",
    "SUPPORT_ROLE_RELIEF",
    "SUPPORT_ROLE_STAFF_ASSISTANT",
    "SUPPORT_ROLE_TRAINEE",
    "all_position_names",
    "get_position",
    "position_names_by_group",
    "positions_by_group",
]
