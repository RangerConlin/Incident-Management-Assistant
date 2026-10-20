"""ICS 203 uses canonical saved organization data without desktop imports."""
from io import BytesIO

import pytest
from pypdf import PdfReader

from sarapp_db.form_exports import context, organization

from sarapp_db.form_exports.builtins import default_registry
from sarapp_db.form_exports.models import ExportError, ExportRequest, ExportSnapshot
from sarapp_db.form_exports.service import default_service

_service = default_service()


def render_snapshot(snapshot):
    return _service.render_snapshot(snapshot)


def mapped_sheets(snapshot):
    definition = _service.registry.get(snapshot.form_id)
    template = _service.resolver.resolve(definition, snapshot.form_set_id)
    return definition.mapper(snapshot, template)


def load_saved(incident_id, form_id, source_id, period_id, prepared_by, form_set_id=None):
    definition = _service.registry.get(form_id)
    request = ExportRequest(incident_id, form_id, source_id, period_id, prepared_by, form_set_id)
    return definition.builder(request, definition)


def test_context_requires_explicit_period_and_rejects_record_selection(monkeypatch):
    class Repository:
        def __init__(self, *args): pass
        def find_one(self, query): return {"incident_id": "TEST-203"}
    monkeypatch.setattr(context, "get_incident_db", lambda _: object())
    monkeypatch.setattr(context, "ExportReadRepository", Repository)
    for source, period in [(None, None), ("record", 1)]:
        with pytest.raises(ExportError) as error:
            load_saved("TEST-203", "ics_203", source, period, "")
        assert error.value.status_code == 422


def organization_fixture(monkeypatch):
    people = [{"person_record": n, "name": f"Person {n}", "organization": f"Agency {n}"} for n in range(1, 8)]
    class Repository:
        def __init__(self, db, collection): self.collection = collection
        def find_many(self, query, sort=None):
            if self.collection == "personnel":
                assert set(query["person_record"]["$in"]) == {1, 2, 3, 4, 5, 6}
                return people
            if self.collection == "liaison_agencies":
                return [{"int_id": 1, "name": "Partner"}]
            return [{"agency_id": 1, "name": f"Contact {n}"} for n in range(8)]
    monkeypatch.setattr(organization, "ExportReadRepository", Repository)
    monkeypatch.setattr(organization, "get_master_db", lambda: object())
    positions = [
        {"position_id": 1, "title": "Incident Commander", "primary": [
            {"person_record": n} for n in [1, 2, 3, 4]
        ], "deputies": [{"person_record": 5}],
         "staff_assistants": [{"person_record": 6, "trainee": True}, {"person_record": 7, "end_time": "2026-01-01"}]},
        {"position_id": 8, "title": "Operations Section Chief", "classification": "section"},
        {"position_id": 2, "title": "Branch Alpha", "parent_position_id": 8, "classification": "branch", "primary": [{"person_record": 1}]},
        {"position_id": 3, "title": "Air Operations Branch Director", "classification": "branch", "primary": [{"person_record": 2}]},
        *[{"position_id": 10 + n, "title": f"Division {n}", "parent_position_id": 2,
           "classification": "division", "primary": [{"person_record": 3}]} for n in range(7)],
    ]
    return organization.load_organization(object(), positions)


def test_203_resolves_names_paginate_and_preserves_interactive_fields(monkeypatch):
    data = organization_fixture(monkeypatch)
    assert data["organization"]["deputy_incident_commander"]["name"] == "Person 5"
    assert "Person 7" not in str(data)
    assert "Trainee" in str(data)
    assert len(data["org_branches"]) == 1
    assert data["org_branches"][0]["divisions"][6]["name"] == "Division 6"
    snapshot = ExportSnapshot("ics_203", {"name": "Organization export test"},
                              {"start_time": "2026-10-19T10:00:00Z", "end_time": "2026-10-19T20:00:00Z"},
                              [data], "Planner")
    sheets = mapped_sheets(snapshot)
    assert len(sheets) == 2
    assert sheets[0]["ICUCs"] == "Person 1"
    assert sheets[1]["ICUCs"] == "Person 4"
    assert sheets[0]["Deputy_2"] == "Person 5"
    assert sheets[0]["Air Ops Branch Dir"] == "Person 2"
    assert sheets[1]["NameRow2"] == "Contact 7"
    assert sheets[1]["Branch Director 1"] == "Branch Alpha"
    assert sheets[1]["Division/Group Identifier 1"] == "Division 5"
    pdf = PdfReader(BytesIO(render_snapshot(snapshot)))
    fields = pdf.get_fields()
    assert fields["sheet_2.ICUCs"]["/V"] == "Person 4"
    assert not fields["sheet_1.Signature_7"].get("/V")
    text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    assert "Division 6" in text and "Contact 7" in text


def test_missing_assignee_is_an_error(monkeypatch):
    class Repository:
        def __init__(self, *args): pass
        def find_many(self, *args, **kwargs): return []
    monkeypatch.setattr(organization, "ExportReadRepository", Repository)
    monkeypatch.setattr(organization, "get_master_db", lambda: object())
    with pytest.raises(ExportError) as error:
        organization.load_organization(object(), [{"title": "Incident Commander", "primary": [{"person_record": 99}]}])
    assert error.value.status_code == 422


@pytest.mark.parametrize("form_set", ["fema", "ics_canada", "uscg"])
def test_every_203_set_uses_approved_fields_and_retains_signatures_blank(monkeypatch, form_set):
    data = organization_fixture(monkeypatch)
    snapshot = ExportSnapshot("ics_203", {"name": "Organization export test"},
                              {"start_time": "2026-10-19T10:00:00Z", "end_time": "2026-10-19T20:00:00Z"},
                              [data], "Planner", form_set, "Planning Section Chief")
    pdf = PdfReader(BytesIO(render_snapshot(snapshot)))
    fields = pdf.get_fields()
    if form_set == "ics_canada":
        assert fields["sheet_1.5. INCIDENT COMMAND AND STAFF Inident Cmndr/Unified Cmndrs A"]["/V"] == "Person 1"
        assert fields["sheet_1.5.uc_name1"]["/V"] == "Person 2"
        assert fields["sheet_1.5.uc_name2"]["/V"] == "Person 3"
        assert fields["sheet_2.5. INCIDENT COMMAND AND STAFF Inident Cmndr/Unified Cmndrs A"]["/V"] == "Person 4"
    assert any(f.get("/V") == "Planner" for f in fields.values())
    assert all(not f.get("/V") for name, f in fields.items() if "Signature" in name)
    from sarapp_db.form_exports.pdf import _widgets
    for name, widgets in _widgets(pdf).items():
        field = fields.get(name)
        if not field or not field.get("/V"):
            continue
        for widget in widgets:
            effective = widget.get("/V")
            parent = widget.get("/Parent")
            while effective is None and parent:
                node = parent.get_object()
                effective = node.get("/V")
                parent = node.get("/Parent")
            assert str(effective) == str(field["/V"])
            assert widget.get("/AP", {}).get("/N") is not None


def test_unknown_form_set_is_rejected_before_database_access():
    with pytest.raises(ExportError) as error:
        load_saved("TEST-203", "ics_203", None, 1, "", "../../invalid")
    assert error.value.status_code == 422


def test_canada_operational_period_matches_widget_geometry():
    snapshot = ExportSnapshot("ics_203", {"name": "Header"},
                              {"start_time": "2026-10-19T10:00:00Z", "end_time": "2026-10-20T20:00:00Z"},
                              [{}], form_set_id="ics_canada")
    fields = mapped_sheets(snapshot)[0]
    assert fields["Text17.0.0"] == "10/19/2026"  # left/top: from date
    assert fields["Text17.0.1"] == "10/20/2026"  # left/bottom: to date
    assert fields["Text17.2"] == "1000 UTC"       # right/top: from time
    assert fields["Text17.1"] == "2000 UTC"       # right/bottom: to time


def test_uscg_resolves_selected_icp_facility_name(monkeypatch):
    class Repository:
        def __init__(self, db, collection): self.collection = collection
        def find_one(self, query):
            if self.collection == "incident_profile":
                return {"name": "Incident", "icp_facility_id": "facility-1"}
            if self.collection == "operational_periods": return {"int_id": 7}
            assert query["_id"] == "facility-1"
            assert query["incident_id"] == "TEST-203"
            return {"name": "Saved command post"}
        def find_many(self, *args, **kwargs): return []
    monkeypatch.setattr(context, "get_incident_db", lambda _: object())
    monkeypatch.setattr(context, "ExportReadRepository", Repository)
    monkeypatch.setattr(organization, "load_organization", lambda *args: {})
    result = load_saved("TEST-203", "ics_203", None, 7, "", "uscg")
    assert mapped_sheets(result)[0]["2 Incident Location"] == "Saved command post"
