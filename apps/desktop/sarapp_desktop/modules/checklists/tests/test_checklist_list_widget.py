from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import modules.checklists.api as api
from modules.checklists.widgets.checklist_list_widget import ChecklistListWidget


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _checklist(**overrides):
    base = {
        "id": "c1",
        "name": "Safety Inspection",
        "status": "in_progress",
        "owner_person_record": None,
        "template_id": None,
        "updated_at": "2026-01-01T10:00:00+00:00",
        "completed_at": None,
        "sections": [{"id": "s1", "items": [{"id": "i1", "item_type": "checkbox", "required": True, "response": None}]}],
    }
    base.update(overrides)
    return base


def test_loading_incident_checklists_populates_table(monkeypatch) -> None:
    app = _app()
    monkeypatch.setattr(api, "list_checklists", lambda incident_id, **kw: [_checklist()])
    monkeypatch.setattr(api, "list_templates", lambda **kw: [])
    widget = ChecklistListWidget("INC1")
    app.processEvents()
    assert widget.table.rowCount() == 1
    assert widget.table.item(0, 0).text() == "Safety Inspection"


def test_switching_incident_reloads_and_clears_stale_rows(monkeypatch) -> None:
    app = _app()
    calls: list[str] = []

    def fake_list(incident_id, **kw):
        calls.append(incident_id)
        return [_checklist(id=f"c-{incident_id}", name=f"Checklist for {incident_id}")]

    monkeypatch.setattr(api, "list_checklists", fake_list)
    monkeypatch.setattr(api, "list_templates", lambda **kw: [])
    widget = ChecklistListWidget("INC1")
    app.processEvents()
    assert widget.table.item(0, 0).text() == "Checklist for INC1"

    widget.set_incident("INC2")
    app.processEvents()
    assert widget.table.item(0, 0).text() == "Checklist for INC2"
    assert calls == ["INC1", "INC2"]


def test_status_filter(monkeypatch) -> None:
    app = _app()
    rows = [_checklist(id="c1", name="A", status="not_started"), _checklist(id="c2", name="B", status="completed")]
    monkeypatch.setattr(api, "list_checklists", lambda incident_id, **kw: rows)
    monkeypatch.setattr(api, "list_templates", lambda **kw: [])
    widget = ChecklistListWidget("INC1")
    app.processEvents()
    assert widget.table.rowCount() == 2

    widget.status_combo.setCurrentText("Completed")
    app.processEvents()
    assert widget.table.rowCount() == 1
    assert widget.table.item(0, 0).text() == "B"


def test_search_filter(monkeypatch) -> None:
    app = _app()
    rows = [_checklist(id="c1", name="Radio Check"), _checklist(id="c2", name="Vehicle Inspection")]
    monkeypatch.setattr(api, "list_checklists", lambda incident_id, **kw: rows)
    monkeypatch.setattr(api, "list_templates", lambda **kw: [])
    widget = ChecklistListWidget("INC1")
    app.processEvents()

    widget.search_edit.setText("radio")
    app.processEvents()
    assert widget.table.rowCount() == 1
    assert widget.table.item(0, 0).text() == "Radio Check"


def test_failures_only_filter(monkeypatch) -> None:
    app = _app()
    failed_item = {
        "id": "f1",
        "item_type": "pass_fail_na",
        "response": {"value": "fail", "na": False},
    }
    rows = [
        _checklist(id="c1", name="Has Failure", sections=[{"id": "s1", "items": [failed_item]}]),
        _checklist(id="c2", name="Clean"),
    ]
    monkeypatch.setattr(api, "list_checklists", lambda incident_id, **kw: rows)
    monkeypatch.setattr(api, "list_templates", lambda **kw: [])
    widget = ChecklistListWidget("INC1")
    app.processEvents()

    widget.failures_only_check.setChecked(True)
    app.processEvents()
    assert widget.table.rowCount() == 1
    assert widget.table.item(0, 0).text() == "Has Failure"


def test_update_checklist_in_place_does_not_requery(monkeypatch) -> None:
    app = _app()
    call_count = {"n": 0}

    def fake_list(incident_id, **kw):
        call_count["n"] += 1
        return [_checklist()]

    monkeypatch.setattr(api, "list_checklists", fake_list)
    monkeypatch.setattr(api, "list_templates", lambda **kw: [])
    widget = ChecklistListWidget("INC1")
    app.processEvents()
    assert call_count["n"] == 1

    updated = _checklist(status="completed", name="Safety Inspection")
    widget.update_checklist_in_place(updated)
    app.processEvents()
    assert call_count["n"] == 1  # no extra network call
    assert widget.table.item(0, 1).text() == "Completed"
