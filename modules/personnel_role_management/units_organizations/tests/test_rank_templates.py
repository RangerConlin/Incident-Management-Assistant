from __future__ import annotations

import importlib


def test_create_and_replace_ranks(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKIN_DATA_DIR", str(tmp_path))
    import utils.db as udb
    import utils.context as uctx
    importlib.reload(udb)
    importlib.reload(uctx)

    from modules.personnel_role_management.units_organizations.controller import (
        UnitsOrganizationsController,
    )

    ctl = UnitsOrganizationsController()

    payload = {
        "name": "Test Template",
        "description": "",
        "organization_type_id": None,
        "is_template": 1,
        "is_system_template": 0,
        "is_active": 1,
        "sort_order": 0,
    }
    ranks = [
        {"sort_order": 0, "rank_code": "A", "rank_name": "Alpha", "short_display": "A"},
        {"sort_order": 1, "rank_code": "B", "rank_name": "Bravo", "short_display": "B"},
    ]

    rid = ctl.save_rank_structure_with_ranks(None, payload, ranks)
    listed = ctl.list_ranks(rid)
    assert [r["rank_code"] for r in listed] == ["A", "B"]

    # Replace ranks
    ranks2 = [
        {"sort_order": 0, "rank_code": "C", "rank_name": "Charlie", "short_display": "C"}
    ]
    ctl.save_rank_structure_with_ranks(rid, payload, ranks2)
    listed2 = ctl.list_ranks(rid)
    assert [r["rank_code"] for r in listed2] == ["C"]
