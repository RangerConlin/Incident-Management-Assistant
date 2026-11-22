"""Phase 4D: the compact "Checklists" section embedded in Assignment and
Schedule Activity detail dialogs."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

import modules.checklists.api as checklist_api
from modules.plannedtoolkit.widgets.checklist_links_section import ChecklistLinksSection


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _checklist(**overrides) -> dict:
    base = {
        "id": "c1",
        "name": "Equipment Check",
        "status": "in_progress",
        "sections": [{"id": "s1", "items": [{"id": "i1", "item_type": "checkbox", "response": None}]}],
    }
    base.update(overrides)
    return base


def test_shows_no_checklists_linked_when_empty(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(checklist_api, "list_checklists", lambda *a, **k: [])
    section = ChecklistLinksSection("INC1", "planned_quick_assignment", "INC1-PLAN-QA-1")
    assert section.list_widget.count() == 1
    assert section.list_widget.item(0).text() == "No checklists linked."


def test_renders_linked_checklist_with_status_and_progress(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(checklist_api, "list_checklists", lambda *a, **k: [_checklist()])
    section = ChecklistLinksSection("INC1", "planned_quick_assignment", "INC1-PLAN-QA-1")
    assert section.list_widget.count() == 1
    text = section.list_widget.item(0).text()
    assert "Equipment Check" in text
    assert "In Progress" in text
    assert "0/1" in text


def test_renders_unresolved_failure_count(monkeypatch) -> None:
    _app()
    failed_item = {"id": "f1", "item_type": "pass_fail_na", "response": {"value": "fail", "na": False}}
    checklist = _checklist(sections=[{"id": "s1", "items": [failed_item]}])
    monkeypatch.setattr(checklist_api, "list_checklists", lambda *a, **k: [checklist])
    section = ChecklistLinksSection("INC1", "planned_quick_assignment", "INC1-PLAN-QA-1")
    assert "unresolved failure" in section.list_widget.item(0).text()


def test_remove_calls_api_after_confirmation(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(checklist_api, "list_checklists", lambda *a, **k: [_checklist()])
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    section = ChecklistLinksSection("INC1", "planned_quick_assignment", "INC1-PLAN-QA-1")

    calls = []
    monkeypatch.setattr(
        checklist_api,
        "remove_link",
        lambda incident_id, checklist_id, *, record_type, record_id: calls.append(
            (incident_id, checklist_id, record_type, record_id)
        ),
    )
    section._on_remove("c1")
    assert calls == [("INC1", "c1", "planned_quick_assignment", "INC1-PLAN-QA-1")]


def test_remove_declined_does_not_call_api(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(checklist_api, "list_checklists", lambda *a, **k: [_checklist()])
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
    section = ChecklistLinksSection("INC1", "planned_quick_assignment", "INC1-PLAN-QA-1")

    calls = []
    monkeypatch.setattr(
        checklist_api,
        "remove_link",
        lambda *a, **k: calls.append(1),
    )
    section._on_remove("c1")
    assert calls == []


def test_link_existing_excludes_already_linked_and_calls_add_link(monkeypatch) -> None:
    _app()
    all_checklists = [_checklist(id="c1", name="A"), _checklist(id="c2", name="B")]
    already_linked = [_checklist(id="c1", name="A")]

    def fake_list(incident_id, *, linked_record_type=None, linked_record_id=None, **kw):
        if linked_record_type:
            return already_linked
        return all_checklists

    monkeypatch.setattr(checklist_api, "list_checklists", fake_list)
    section = ChecklistLinksSection("INC1", "planned_quick_assignment", "INC1-PLAN-QA-1")

    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    calls = []
    monkeypatch.setattr(
        checklist_api,
        "add_link",
        lambda incident_id, checklist_id, *, record_type, record_id: calls.append(
            (incident_id, checklist_id, record_type, record_id)
        ),
    )
    section._on_link_existing()
    assert calls == [("INC1", "c2", "planned_quick_assignment", "INC1-PLAN-QA-1")]


def test_link_existing_with_no_candidates_shows_message_and_does_not_open_dialog(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(checklist_api, "list_checklists", lambda *a, **k: [_checklist()])

    dialog_opened = []
    monkeypatch.setattr(QDialog, "exec", lambda self: dialog_opened.append(1) or QDialog.DialogCode.Rejected)
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))

    section = ChecklistLinksSection("INC1", "planned_quick_assignment", "INC1-PLAN-QA-1")
    section._on_link_existing()
    assert dialog_opened == []
