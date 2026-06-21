from __future__ import annotations

import importlib


def test_seed_types_and_templates_present(tmp_path, monkeypatch):
    # Point data dir to a temp location before importing modules that open DBs
    monkeypatch.setenv("CHECKIN_DATA_DIR", str(tmp_path))

    # Reload connection helpers so they resolve the temp directory
    import utils.db as udb
    import utils.context as uctx
    importlib.reload(udb)
    importlib.reload(uctx)

    from modules.personnel.units_organizations.models.repository import (
        UnitsOrganizationsRepository,
    )

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

    # Use a raw connection to count ranks
    from utils.db import get_master_conn

    with get_master_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM ranks WHERE rank_structure_id = ?",
            (int(fd["id"]),),
        ).fetchone()[0]
        assert count >= 6  # at least several ranks seeded


def test_seeding_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKIN_DATA_DIR", str(tmp_path))
    import utils.db as udb
    import utils.context as uctx
    importlib.reload(udb)
    importlib.reload(uctx)

    from modules.personnel.units_organizations.models.repository import (
        UnitsOrganizationsRepository,
    )

    # First instantiation seeds
    UnitsOrganizationsRepository()
    # Second instantiation should not duplicate
    UnitsOrganizationsRepository()

    from utils.db import get_master_conn

    with get_master_conn() as conn:
        rows = conn.execute(
            "SELECT COUNT(*) FROM rank_structures WHERE name = ? AND is_system_template = 1",
            ("Fire Department (Standard)",),
        ).fetchone()[0]
        assert rows == 1
