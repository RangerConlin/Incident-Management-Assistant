from __future__ import annotations

from io import BytesIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader

from sarapp_db.form_exports.pdf import _widgets
from sarapp_db.form_exports.templates import ASSETS
from dataclasses import replace
from sarapp_db.form_exports.registry import ExportRegistry
from sarapp_db.form_exports.service import FormExportService
from sarapp_db.api.routers import form_exports

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


def snapshot(form: str, records: list[dict] | None = None) -> ExportSnapshot:
    form_set_id = default_registry().get(form).default_set
    return ExportSnapshot(form, {"name": "Export test incident", "incident_number": "EXPORT-1"},
                          {"number": 1, "start_time": "2026-10-20T00:00:00Z", "end_time": "2026-10-20T12:00:00Z"},
                          records if records is not None else [{"id": "r1", "title": "Water", "text": "Confirm access", "code": "OBJ-1", "priority": "IMMEDIATE", "created_utc": "2026-10-20T01:02:03Z", "created_by_id": "Requester", "assignment_name": "Access", "description": "Confirm access to staging", "location": "Staging", "sitrep_number": 1, "summary": "Access confirmed", "prepared_by": "Planner", "created_at": "2026-10-20T01:02:03Z", "meeting_date": "2026-10-20", "start_time": "10:00:00", "end_time": "11:00:00", "resource_name": "Responder", "entity_type": "personnel", "checked_in_time": "2026-10-20T01:02:03Z"}], "Planner", form_set_id)


@pytest.mark.parametrize("form", [d.form_id for d in default_registry().definitions()])
def test_every_export_has_exact_template_fields_and_valid_interactive_values(form):
    data = snapshot(form)
    available = PdfReader(ASSETS / f"{form}.pdf").get_fields() or {}
    for values in mapped_sheets(data):
        assert set(values).issubset(available)
    result = PdfReader(BytesIO(render_snapshot(data)))
    fields = result.get_fields() or {}
    assert fields
    assert len(result.pages) >= 2  # Includes a saved-source continuation.
    assert any("Export test incident" in str(f.get("/V", "")) for f in fields.values())
    widgets = _widgets(result)
    for name, field in fields.items():
        if not field.get("/V") or name not in widgets:
            continue
        for widget in widgets[name]:
            effective = widget.get("/V")
            parent = widget.get("/Parent")
            while effective is None and parent:
                node = parent.get_object()
                effective = node.get("/V")
                parent = node.get("/Parent")
            assert str(effective) == str(field["/V"])
            appearance = widget.get("/AP", {}).get("/N")
            assert appearance is not None
            appearance = appearance.get_object()
            if field.get("/FT") == "/Btn":
                assert str(field["/V"]) in appearance
            elif hasattr(appearance, "get_data"):
                assert appearance.get_data()
                if str(field["/V"]) == "Export test incident":
                    assert b"Export test incident" in appearance.get_data()


def test_resource_request_overflow_keeps_all_rows_and_never_fills_approval_signatures():
    data = snapshot("ics_213rr")
    data.records[0]["items"] = [{"id": str(n), "description": f"Resource item {n}", "quantity": n + 1, "kind": "SUPPLY", "unit": "case"} for n in range(20)]
    assert len(mapped_sheets(data)) == 3
    result = PdfReader(BytesIO(render_snapshot(data)))
    fields = result.get_fields() or {}
    assert str(fields["sheet_3.QtyRow2"]["/V"]) == "20"
    assert any("Resource item 19" in (page.extract_text() or "") for page in result.pages)
    assert not fields["sheet_1.14. Approval Signature of Authorized Log Rep"].get("/V")


def test_long_text_has_visible_continuation_and_lossless_supplement():
    data = snapshot("ics_202", [{"text": "Continuation content " * 700, "code": "OBJ-1"}])
    result = PdfReader(BytesIO(render_snapshot(data)))
    assert "see annex" in str(result.get_fields()["sheet_1.3 Objectives"]["/V"])
    assert "Full text for continued fields" in "\n".join(page.extract_text() or "" for page in result.pages)
    assert "Continuation content" in result.pages[-1].extract_text()


def test_safety_and_checkin_rows_paginate_without_truncating():
    data = snapshot("ics_215a")
    data.records[0]["hazards"] = [{"hazard_type_text": f"Hazard {n}"} for n in range(31)]
    assert len(mapped_sheets(data)) == 3
    data = snapshot("ics_211", [{"resource_name": str(n)} for n in range(25)])
    assert len(mapped_sheets(data)) == 4
    data = snapshot("ics_215")
    data.records[0]["resources"] = [{"resource_type_text": str(n), "quantity_required": 1} for n in range(25)]
    assert len(mapped_sheets(data)) == 3


def test_download_route_returns_pdf_and_safe_filename_without_writing_data(monkeypatch):
    app = FastAPI()
    app.include_router(form_exports.router, prefix="/api")
    registry = ExportRegistry()
    definition = default_registry().get("ics_213rr")
    registry.register(replace(definition, builder=lambda *args: snapshot("ics_213rr")))
    monkeypatch.setattr(form_exports, "service", FormExportService(registry))
    with TestClient(app) as client:
        response = client.post("/api/incidents/test/form-exports", json={"form_id": "ics_213rr", "source_id": "bad\r\nname"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "bad__name.pdf" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "no-store"
    assert response.content.startswith(b"%PDF")


def test_context_reads_canonical_sources_and_never_runs_id_repairs(monkeypatch):
    from sarapp_db.form_exports import context
    calls = []
    data = {
        "incident_profile": [{"incident_id": "inc", "name": "Incident"}],
        "work_assignments": [{"int_id": 7, "operational_period_id": 2}],
        "operational_periods": [{"int_id": 2, "number": 2}],
    }
    class Repository:
        def __init__(self, db, collection): self.collection = collection
        def find_one(self, query):
            calls.append((self.collection, query))
            return next((r for r in data.get(self.collection, []) if all(r.get(k) == v for k, v in query.items() if k != "deleted")), None)
        def find_many(self, query, sort=None):
            calls.append((self.collection, query))
            return []
    monkeypatch.setattr(context, "get_incident_db", lambda incident: object())
    monkeypatch.setattr(context, "ExportReadRepository", Repository)
    result = load_saved("inc", "ics_204", "7", None, "Planner")
    assert result.period["int_id"] == 2
    assert result.records[0]["int_id"] == 7
    with pytest.raises(ExportError) as error:
        load_saved("inc", "ics_204", "7", 3, "Planner")
    assert error.value.status_code == 422
    with pytest.raises(ExportError) as error:
        load_saved("inc", "ics_213rr", "missing", None, "Planner")
    assert error.value.status_code == 404
    with pytest.raises(ExportError):
        load_saved("inc", "../../secret", None, None, "Planner")


def test_shared_app_mounts_exports_only_for_incident_servers():
    from sarapp_db.api.app import create_app
    def paths(mode): return {r.path for r in create_app(mode=mode).routes}
    assert "/api/incidents/{incident_id}/form-exports" in paths("full")
    assert "/api/incidents/{incident_id}/form-exports" not in paths("master_only")
