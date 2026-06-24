from __future__ import annotations

from modules.personnel.units_organizations.models.repository import (
    UnitsOrganizationsRepository,
)


def test_seed_types_and_templates_present(org_app_client):
    repo = UnitsOrganizationsRepository()

    types = repo.list_organization_types(include_inactive=True)
    names = {t["name"] for t in types}
    assert {
        "Air Agency",
        "Ground SAR",
        "Law Enforcement",
        "Fire/Rescue",
        "EMS",
        "Government",
        "Volunteer Organization",
        "NGO",
        "Federal",
        "State",
        "County",
        "Municipal",
        "Military",
        "Private Contractor",
        "Amateur Radio",
        "Aviation Support",
        "Communications Unit",
        "Other",
    }.issubset(names)

    templates = repo.list_rank_structures(include_inactive=True)
    template_names = {t["name"] for t in templates}
    assert {
        "Fire Department (Standard)",
        "Law Enforcement (Standard)",
        "EMS (Standard)",
        "Search and Rescue (Standard)",
        "Volunteer / NGO (Standard)",
    }.issubset(template_names)

    # Verify ranks for a known template exist
    fd = next(t for t in templates if t["name"] == "Fire Department (Standard)")
    ranks = repo.list_ranks(fd["int_id"])
    assert len(ranks) >= 6  # at least several ranks seeded


def test_seeding_is_idempotent(org_app_client):
    # First instantiation seeds
    UnitsOrganizationsRepository()
    # Second instantiation should not duplicate
    UnitsOrganizationsRepository()

    structures = org_app_client.get("/api/master/rank-structures")
    matches = [s for s in structures if s["name"] == "Fire Department (Standard)" and s.get("is_system_template")]
    assert len(matches) == 1
