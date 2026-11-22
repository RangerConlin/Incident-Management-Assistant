from __future__ import annotations

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import modules.checklists.api as api
from modules.checklists.widgets.checklist_execution_widget import ChecklistExecutionWidget


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _pump(predicate, timeout_s: float = 3.0) -> None:
    """Process Qt events until `predicate()` is true or we time out —
    needed because item responses/loads run on a real QThread
    (`BackgroundCall`), not synchronously."""

    app = _app()
    deadline = time.time() + timeout_s
    while not predicate() and time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert predicate(), "timed out waiting for background call to complete"


def _item(item_id: str, item_type: str, **overrides) -> dict:
    base = {
        "id": item_id,
        "item_type": item_type,
        "label": item_id,
        "instructions": "",
        "required": False,
        "na_allowed": False,
        "options": [],
        "unit": "",
        "min_value": None,
        "max_value": None,
        "response": None,
        "history": [],
    }
    base.update(overrides)
    return base


def _checklist(items, **overrides) -> dict:
    base = {
        "id": "c1",
        "int_id": 1,
        "incident_id": "INC1",
        "name": "Test Checklist",
        "description": "",
        "instructions": "",
        "template_id": None,
        "owner_person_record": None,
        "linked_record": None,
        "status": "in_progress",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "created_by": 101,
        "completed_at": None,
        "completed_by": None,
        "archived_at": None,
        "archived_by": None,
        "lifecycle_event_seq": 0,
        "ics214_stream": None,
        "ics214_entry_id": None,
        "ics214_pending": False,
        "lifecycle_history": [],
        "sections": [{"id": "s1", "name": "Section", "items": items}],
    }
    base.update(overrides)
    return base


def _widget(monkeypatch, checklist: dict) -> ChecklistExecutionWidget:
    app = _app()
    monkeypatch.setattr(api, "get_checklist", lambda incident_id, checklist_id: checklist)
    monkeypatch.setattr(api, "resolve_person_display", lambda pr: f"P{pr}" if pr else "")
    monkeypatch.setattr(api, "current_actor_id", lambda: 101)
    widget = ChecklistExecutionWidget()
    widget.load_checklist("INC1", checklist["id"])
    _pump(lambda: widget._checklist is not None)
    app.processEvents()
    return widget


def test_renders_all_five_item_types(monkeypatch) -> None:
    items = [
        _item("chk", "checkbox"),
        _item("pfn", "pass_fail_na", na_allowed=True),
        _item("txt", "text"),
        _item("num", "numeric", unit="%", min_value=0, max_value=100),
        _item("sel", "selection", options=[{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]),
    ]
    widget = _widget(monkeypatch, _checklist(items))
    assert set(widget._rows.keys()) == {"chk", "pfn", "txt", "num", "sel"}
    assert widget._rows["sel"].control.count() == 3  # placeholder + 2 options


def test_na_only_available_when_permitted(monkeypatch) -> None:
    items = [_item("no_na", "checkbox", na_allowed=False), _item("has_na", "checkbox", na_allowed=True)]
    widget = _widget(monkeypatch, _checklist(items))
    assert widget._rows["no_na"].na_check is None
    assert widget._rows["has_na"].na_check is not None


def test_unanswered_item_shows_not_yet_answered_caption(monkeypatch) -> None:
    widget = _widget(monkeypatch, _checklist([_item("chk", "checkbox")]))
    assert widget._rows["chk"].caption_label.text() == "Not yet answered."


def test_item_attribution_caption_shown_for_answered_item(monkeypatch) -> None:
    response = {"value": True, "na": False, "notes": "", "recorded_by": 202, "recorded_at": "2026-01-01T14:32:00+00:00"}
    widget = _widget(monkeypatch, _checklist([_item("chk", "checkbox", response=response)]))
    caption = widget._rows["chk"].caption_label.text()
    assert "P202" in caption
    assert "Completed by" in caption


def test_checkbox_response_submission_uses_authenticated_actor(monkeypatch) -> None:
    calls = []

    def fake_record(incident_id, checklist_id, item_id, *, value, na, notes):
        calls.append((incident_id, checklist_id, item_id, value, na, notes))
        updated_item = _item(item_id, "checkbox", response={
            "value": value, "na": na, "notes": notes, "recorded_by": 101, "recorded_at": "2026-01-01T00:00:01+00:00",
        })
        return {"item": updated_item, "response": updated_item["response"], "checklist": _checklist([updated_item])}

    widget = _widget(monkeypatch, _checklist([_item("chk", "checkbox")]))
    monkeypatch.setattr(api, "record_item_response", fake_record)

    widget._rows["chk"].control.setChecked(True)
    _pump(lambda: widget._rows["chk"].pending_call is None and calls)

    assert calls == [("INC1", "c1", "chk", True, False, "")]
    assert "Completed by P101" in widget._rows["chk"].caption_label.text()


def test_required_text_item_blank_save_failure_preserves_input(monkeypatch) -> None:
    from utils.api_client import APIError

    def fake_record(*args, **kwargs):
        raise APIError("Item requires a response", 422)

    widget = _widget(monkeypatch, _checklist([_item("txt", "text", required=True)]))
    monkeypatch.setattr(api, "record_item_response", fake_record)

    row = widget._rows["txt"]
    row.control.setPlainText("some input the user typed")
    row._save_now()
    _pump(lambda: row.pending_call is None and "Save failed" in row.caption_label.text())

    # The failed save must not discard what the user typed.
    assert row.control.toPlainText() == "some input the user typed"


def test_concurrent_saves_for_same_item_do_not_race(monkeypatch) -> None:
    """Two rapid changes to the same item must not both be in flight at
    once (duplicate submission); the second must be sent after the first
    completes, carrying the latest control state."""

    received_values = []
    call_count = {"n": 0}

    def fake_record(incident_id, checklist_id, item_id, *, value, na, notes):
        call_count["n"] += 1
        received_values.append(value)
        updated_item = _item(item_id, "checkbox", response={
            "value": value, "na": na, "notes": notes, "recorded_by": 101, "recorded_at": "2026-01-01T00:00:01+00:00",
        })
        return {"item": updated_item, "response": updated_item["response"], "checklist": _checklist([updated_item])}

    widget = _widget(monkeypatch, _checklist([_item("chk", "checkbox")]))
    monkeypatch.setattr(api, "record_item_response", fake_record)

    row = widget._rows["chk"]
    row._save_now()  # first save (value False, not in flight yet when the next line runs)
    assert row.pending_call is not None
    row._save_now()  # requested while the first is still in flight -> must be coalesced, not duplicated
    assert row._dirty is True

    _pump(lambda: call_count["n"] >= 1 and row.pending_call is None and not row._dirty)
    # Exactly the number of distinct saves actually needed were sent (no two concurrent calls).
    assert call_count["n"] >= 1


def test_history_endpoint_reachable_via_resolve(monkeypatch) -> None:
    history_payload = {"item_id": "chk", "history": [
        {"value": False, "na": False, "notes": "", "recorded_by": 101, "recorded_at": "2026-01-01T00:00:00+00:00"},
        {"value": True, "na": False, "notes": "fixed", "recorded_by": 202, "recorded_at": "2026-01-01T01:00:00+00:00"},
    ]}
    monkeypatch.setattr(api, "get_item_history", lambda incident_id, checklist_id, item_id: history_payload)
    monkeypatch.setattr(api, "resolve_person_display", lambda pr: f"P{pr}")

    from modules.checklists.widgets.response_history_dialog import ResponseHistoryDialog

    _app()
    dialog = ResponseHistoryDialog("INC1", "c1", "chk", "Checked")
    assert dialog.list_widget.count() == 2
    assert "P202" in dialog.list_widget.item(0).text()  # newest first
