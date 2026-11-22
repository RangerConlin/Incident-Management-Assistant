from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import modules.checklists.api as api
from modules.checklists.widgets.checklists_tab import ChecklistsTab


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_incident_switch_clears_detail_and_reloads_list(monkeypatch) -> None:
    app = _app()
    calls: list[str] = []

    def fake_list(incident_id, **kw):
        calls.append(incident_id)
        return []

    monkeypatch.setattr(api, "list_checklists", fake_list)
    monkeypatch.setattr(api, "list_templates", lambda **kw: [])

    tab = ChecklistsTab("INC1")
    app.processEvents()
    assert calls == ["INC1"]

    tab.set_incident("INC2")
    app.processEvents()
    assert calls == ["INC1", "INC2"]
    assert tab.execution_widget.incident_id is None
    assert tab.execution_widget.checklist_id is None


def test_selecting_checklist_loads_it_in_execution_widget(monkeypatch) -> None:
    app = _app()
    checklist = {
        "id": "c1",
        "name": "Radio Check",
        "status": "not_started",
        "owner_person_record": None,
        "template_id": None,
        "updated_at": "2026-01-01T00:00:00+00:00",
        "completed_at": None,
        "sections": [],
    }
    monkeypatch.setattr(api, "list_checklists", lambda incident_id, **kw: [checklist])
    monkeypatch.setattr(api, "list_templates", lambda **kw: [])
    monkeypatch.setattr(api, "get_checklist", lambda incident_id, checklist_id: {**checklist, "sections": []})
    monkeypatch.setattr(api, "current_actor_id", lambda: 101)

    tab = ChecklistsTab("INC1")
    app.processEvents()
    tab.list_widget.select_checklist_id("c1")
    app.processEvents()

    assert tab.execution_widget.checklist_id == "c1"
