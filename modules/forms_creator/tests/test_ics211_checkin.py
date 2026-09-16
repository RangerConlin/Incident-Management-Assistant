"""Coverage for the ICS-211 check-in list binding (context.py + pdf_filler.py)."""

from __future__ import annotations

from modules.forms_creator.context import FormDataContext
from modules.forms_creator.pdf_filler.pdf_filler import PDFFiller


def test_row_fields_apply_transform(tmp_path):
    """row_fields entries with a 'transform' key format the value like fields[] does."""
    filler = PDFFiller.__new__(PDFFiller)
    filler.mapping = {}
    rg = {
        "data_key": "rows",
        "rows_per_page": [2],
        "row_fields": [
            {"row": 1, "pdf_field": "DT1", "source_key": "when", "transform": "datetime_human"},
            {"row": 1, "pdf_field": "Name1", "source_key": "name"},
        ],
    }
    data = {"rows": [{"when": "2026-07-03T07:30:19+00:00", "name": "Avery Johnson"}]}
    field_values: dict = {}
    warnings = filler._fill_col_patterns_group(rg, data, field_values, [])
    assert warnings == []
    assert field_values["Name1"] == "Avery Johnson"
    assert field_values["DT1"] != "2026-07-03T07:30:19+00:00"
    assert "07/03/26" in field_values["DT1"]


def test_build_checkin_list_splits_resource_types(monkeypatch):
    def fake_get(path, **params):
        if path == "/api/incidents/inc1/resource-status":
            return [
                {
                    "entity_type": "personnel",
                    "record_id": 1,
                    "resource_name": "Avery Johnson",
                    "resource_id": "1",
                    "status": "Assigned",
                    "checked_in_time": "2026-07-03T07:30:19+00:00",
                    "assigned_to": "Team 1",
                },
                {
                    "entity_type": "vehicle",
                    "record_id": 10,
                    "resource_name": "Engine 2",
                    "resource_id": "20050",
                    "status": "Available",
                    "checked_in_time": None,
                    "assigned_to": None,
                },
                {
                    "entity_type": "personnel",
                    "record_id": 2,
                    "resource_name": "Not Checked In",
                    "status": "Pending",
                },
            ]
        if path == "/api/master/personnel/1":
            return {"name": "Avery Johnson", "phone": "555-1234", "home_unit": "GLR-MI-063", "primary_role": "GTL"}
        if path == "/api/master/vehicles/10":
            return {"organization": "GLR-MI-007", "vehicle_type": "12 Pax"}
        if path == "/api/incidents/inc1/checkin/teams/checked-state":
            return [
                {
                    "name": "Team 1",
                    "team_leader": 1,
                    "members_json": "[1, 2]",
                    "checked_in_at": "2026-07-03T08:00:00+00:00",
                    "assignment": "GT Bravo",
                }
            ]
        if path == "/api/resource-types":
            return []
        return []

    monkeypatch.setattr("modules.forms_creator.context._get", fake_get)

    rows = FormDataContext()._build_checkin_list("inc1")
    categories = {r["category"] for r in rows}
    assert categories == {"Personnel", "Vehicle", "Team"}

    personnel_row = next(r for r in rows if r["category"] == "Personnel")
    assert personnel_row["resource_name_or_id"] == "Avery Johnson"
    assert personnel_row["home_unit"] == "GLR-MI-063"
    assert personnel_row["incident_contact"] == "555-1234"
    assert personnel_row["kind"] == "GTL"

    vehicle_row = next(r for r in rows if r["category"] == "Vehicle")
    assert vehicle_row["agency"] == "GLR-MI-007"
    assert vehicle_row["type"] == "12 Pax"

    team_row = next(r for r in rows if r["category"] == "Team")
    assert team_row["st_or_tf"] == "Strike Team/Task Force"
    assert team_row["leader_name"] == "Avery Johnson"
    assert team_row["total_personnel"] == "2"
    assert team_row["incident_assignment"] == "GT Bravo"
