from __future__ import annotations

from dataclasses import dataclass

from models import queries
from modules.forms_creator.context import FormDataContext


@dataclass(slots=True)
class _Identity:
    name: str = "Ada Lead"
    primary_role: str = "Searcher"
    phone: str = "555-0100"
    callsign: str = "A1"
    rank: str = "LT"
    is_medic: bool = True


class _ApiClient:
    def get(self, path: str):
        assert path == "/api/incidents/INC-1/operations/teams/3"
        return {"member_personnel_ids": [101]}


def test_fetch_team_personnel_allows_identity_without_home_unit(monkeypatch):
    from modules.logistics.checkin import repository as ci_repo
    from utils import api_client as api_client_module
    from utils import incident_context

    monkeypatch.setattr(incident_context, "get_active_incident_id", lambda: "INC-1")
    monkeypatch.setattr(api_client_module, "api_client", _ApiClient())
    monkeypatch.setattr(ci_repo, "get_person_identity", lambda person_id: _Identity())

    rows = queries.fetch_team_personnel(3)

    assert rows == [
        {
            "id": 101,
            "name": "Ada Lead",
            "role": "Searcher",
            "phone": "555-0100",
            "callsign": "A1",
            "identifier": "A1",
            "rank": "LT",
            "organization": "",
            "home_unit": "",
            "agency": "",
            "is_medic": True,
        }
    ]


def test_form_personnel_context_treats_home_unit_as_organization(monkeypatch):
    rows = [
        {"person_record": 1, "name": "Home Unit", "home_unit": "County SAR"},
        {"person_record": 2, "name": "Organization", "organization": "Metro Fire"},
        {"person_record": 3, "name": "Agency", "agency": "State Police"},
    ]

    monkeypatch.setattr("modules.forms_creator.context._get", lambda path, **params: rows)

    personnel = FormDataContext()._build_personnel()

    assert personnel[0]["agency"] == "County SAR"
    assert personnel[0]["organization"] == "County SAR"
    assert personnel[0]["home_unit"] == "County SAR"
    assert personnel[1]["agency"] == "Metro Fire"
    assert personnel[1]["organization"] == "Metro Fire"
    assert personnel[1]["home_unit"] == "Metro Fire"
    assert personnel[2]["agency"] == "State Police"
    assert personnel[2]["organization"] == "State Police"
    assert personnel[2]["home_unit"] == "State Police"
