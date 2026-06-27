from __future__ import annotations

import json
from pathlib import Path

from modules.operations.taskings import repository as repo
from modules.operations.teams.data.team import Team


def test_sar104_mapping_uses_assignment_context():
    mapping_path = Path(r"C:\Users\Brendan\Documents\GitHub\Incident-Management-Assistant\forms\sets\sar\sar_104\mapping.json")
    data = json.loads(mapping_path.read_text(encoding="utf-8"))
    fields = {item["pdf_field"]: item.get("source", "") for item in data["fields"]}

    assert fields["assignment.number"] == "task.task_id"
    assert fields["resource_type"] == "team.resource_type"
    assert fields["personnel.name.1"] == "team.leader_name"
    assert fields["personnel.agency.1"] == "team.leader_agency"
    assert fields["personnel.function.1"] == "team.role"
    assert fields["personnel.function.4"] == "team_members.3.member_role"
    assert fields["previous_search_effort"] == "assignment.ground.previous_search_efforts"
    assert fields["radio_call"] == "radio_call"
    assert fields["maps_attached"] == "maps_attached"
    assert fields["debrief_attached"] == "debrief_attached"
    assert fields["equipment_issued"] == "equipment_issued"

    row_groups = data["row_groups"]
    assert [rg["ref"] for rg in row_groups] == ["team_members"]
    assert row_groups[0]["rows_per_page"] == [8]


def test_sar104_bindings_exist_in_library():
    catalog_path = Path(r"C:\Users\Brendan\Documents\GitHub\Incident-Management-Assistant\forms\binding_catalog.json")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    paths = {item["path"] for item in catalog}

    expected = {
        "task.task_id",
        "task.assignment",
        "team.resource_type",
        "team.role",
        "team.leader_name",
        "team.leader_agency",
        "assignment.ground.previous_search_efforts",
        "assignment.ground.time_allocated",
        "assignment.ground.size_of_assignment",
        "assignment.ground.transport_instructions",
        "assignment.ground.expected_pod.responsive.high",
        "assignment.ground.expected_pod.unresponsive.medium",
        "assignment.ground.expected_pod.clues.low",
        "radio_call",
        "equipment_issued",
        "briefer",
        "time_briefed",
        "time_out",
        "time_in",
        "notes",
        "additional.names",
        "maps_attached",
        "debrief_attached",
        "team_members.0.member_name",
        "team_members.0.member_agency",
        "team_members.0.member_medic",
        "team_members.0.member_role",
    }

    assert expected.issubset(paths)


def test_cap_weather_mappings_reference_shared_weather_payload():
    cap104_mapping = Path(r"C:\Users\Brendan\Documents\GitHub\Incident-Management-Assistant\forms\sets\cap\capf_104\mapping.json")
    cap109_mapping = Path(r"C:\Users\Brendan\Documents\GitHub\Incident-Management-Assistant\forms\sets\cap\capf_109\mapping.json")

    cap104 = json.loads(cap104_mapping.read_text(encoding="utf-8"))
    cap109 = json.loads(cap109_mapping.read_text(encoding="utf-8"))

    cap104_sources = {
        item["pdf_field"]: item.get("source", {}).get("key") if isinstance(item.get("source"), dict) else item.get("source")
        for item in cap104["fields"]
    }
    cap109_sources = {item["pdf_field"]: item.get("source") for item in cap109["fields"]}

    assert cap104_sources["Weather Conditions"] == "weather.conditions"
    assert cap104_sources["Current Local"] == "weather.current.local"
    assert cap104_sources["Current Enroute"] == "weather.current.enroute"
    assert cap104_sources["Current Area of Operations"] == "weather.current.area_of_operations"
    assert cap104_sources["Forecast Local"] == "weather.forecast.local"
    assert cap104_sources["Forecast Enroute"] == "weather.forecast.enroute"
    assert cap104_sources["Forecast Area of Operations"] == "weather.forecast.area_of_operations"
    assert cap109_sources["Text68"] == "weather.current.local"
    assert cap109_sources["Text69"] == "weather.forecast.local"


def test_sar104_export_context_orders_team_and_roster(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(repo.incident_context, "get_active_incident_id", lambda: "INC-1")
    monkeypatch.setattr(
        repo,
        "_task_dict",
        lambda task_id: {
            "int_id": task_id,
            "task_id": "SAR-17",
            "title": "Search line",
            "description": "Sweep the north ridge",
            "location": "North Ridge",
            "assignment": "Search the north ridge",
            "due_time": "2026-06-23T18:00:00",
            "radio_primary": "151.100",
            "radio_alternate": "155.250",
            "radio_emergency": "146.520",
        },
    )
    monkeypatch.setattr(
        repo,
        "get_task_assignment",
        lambda task_id: {
            "ground": {
                "previous_search_efforts": "None",
                "present_search_efforts": "Search from ridge top",
                "time_allocated": "2 hours",
                "size_of_assignment": "4 members",
                "drop_off_instructions": "Stage at gate",
                "pickup_instructions": "Return to ICP",
                "expected_pod": {
                    "responsive": "High",
                    "unresponsive": "Medium",
                    "clues": "Low",
                },
            }
        },
    )
    monkeypatch.setattr(
        repo,
        "list_task_teams",
        lambda task_id: [
            {
                "id": 7,
                "team_id": 7,
                "team_name": "GT-7",
                "team_leader": "Alice Leader",
                "team_leader_phone": "555-0100",
                "status": "Briefed",
                "assigned_ts": "2026-06-23T16:00:00",
                "briefed_ts": "2026-06-23T16:15:00",
                "enroute_ts": "2026-06-23T16:20:00",
                "arrival_ts": "2026-06-23T16:35:00",
                "complete_ts": "",
            }
        ],
    )
    monkeypatch.setattr(
        repo,
        "get_team",
        lambda team_id: Team(
            team_id=team_id,
            name="GT-7",
            callsign="Search One",
            role="Team Leader",
            team_leader_id=101,
            team_leader_phone="555-0100",
            team_type="GT",
            resource_type_id=42,
            status="briefed",
        ),
    )
    monkeypatch.setattr(repo.ApiResourceAssignmentRepository, "get_resource_type_name", lambda self, rid: "Ground Search Team")
    monkeypatch.setattr(
        repo,
        "fetch_team_personnel",
        lambda team_id: [
            {"id": 101, "name": "Alice Leader", "organization": "County SAR", "is_medic": False, "role": "Leader"},
            {"id": 102, "name": "Bob Medic", "organization": "County SAR", "is_medic": True, "role": "Medic"},
            {"id": 103, "name": "Cara Searcher", "organization": "County SAR", "is_medic": False, "role": "Searcher"},
        ],
    )
    monkeypatch.setattr(
        repo,
        "fetch_team_equipment",
        lambda team_id: [{"name": "Rope Kit"}, {"name": "First Aid Pack"}],
    )
    monkeypatch.setattr(
        repo,
        "fetch_team_vehicles",
        lambda team_id: [{"name": "UTV-1"}, {"callsign": "Alpha 1"}],
    )
    monkeypatch.setattr(
        repo,
        "generate_form_pdf",
        lambda form_id, out_path, form_set_id=None, extra_data=None: Path(out_path),
    )
    monkeypatch.setattr(
        repo,
        "_client",
        lambda: type(
            "FakeClient",
            (),
            {
                "get": staticmethod(
                    lambda path, params=None: {
                        "weather_payload": {
                            "metar": {
                                "KCVG": {"station": "KCVG", "raw_text": "KCVG 261651Z 21012KT 10SM SCT040 29/21 A2992"},
                                "KDAY": {"station": "KDAY", "raw_text": "KDAY 261656Z 22010KT 10SM BKN050 28/20 A2990"},
                            },
                            "forecast": {
                                "39.1031,-84.5120": {
                                    "label": "ICP",
                                    "periods": [
                                        {"name": "Today", "temperature": 84, "detailed_text": "Hot and humid"},
                                        {"name": "Tonight", "temperature": 68, "detailed_text": "Chance of storms"},
                                    ],
                                }
                            },
                            "advisories": [{"event": "Heat Advisory"}],
                        },
                        "icao_codes": ["KCVG", "KDAY"],
                    }
                )
            },
        )(),
    )

    context = repo._build_assignment_export_context(17, {"team_id": 7})
    assert context["team"]["leader_name"] == "Alice Leader"
    assert context["team"]["leader_agency"] == "County SAR"
    assert context["team"]["resource_type"] == "Ground Search Team"
    assert context["team_members"][0]["member_name"] == "Alice Leader"
    assert context["team_members"][1]["member_medic"] is True
    assert context["assignment"]["ground"]["expected_pod"]["responsive"]["high"] == "X"
    assert context["radio_call"].startswith("Primary: 151.100")
    assert context["weather"]["current"]["local"].startswith("KCVG:")
    assert "Heat Advisory" in context["weather"]["conditions"]
    assert context["weather_summary"].startswith("Current:")

    exports = repo.export_assignment_forms(17, ["SAR 104"], {"team_id": 7})
    assert len(exports) == 1
    assert exports[0]["form_id"] == "sar_104"
    assert exports[0]["form_set_id"] == "sar"
    assert exports[0]["file_path"].endswith(r"data\exports\INC-1\task_17\sar_104.pdf")
