"""Pure unit tests for the shared Checklist domain logic (no Mongo)."""
from __future__ import annotations

import pytest

from sarapp_db.services import checklist_service as svc


def _item(**overrides) -> dict:
    base = {
        "id": "item-1",
        "item_type": svc.CHECKBOX,
        "label": "Test item",
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


def test_validate_template_shape_rejects_duplicate_item_ids_across_sections() -> None:
    sections = [
        {"id": "s1", "name": "A", "items": [_item(id="dup")]},
        {"id": "s2", "name": "B", "items": [_item(id="dup")]},
    ]
    with pytest.raises(svc.ChecklistValidationError):
        svc.validate_template_shape(sections)


def test_snapshot_sections_deep_copies_and_resets_responses() -> None:
    sections = [{"id": "s1", "name": "A", "items": [_item(response={"value": True})]}]
    snapshot = svc.snapshot_sections(sections)
    snapshot[0]["items"][0]["label"] = "Changed"
    assert sections[0]["items"][0]["label"] == "Test item"
    assert snapshot[0]["items"][0]["response"] is None
    assert snapshot[0]["items"][0]["history"] == []


@pytest.mark.parametrize(
    "item_type,value,expected",
    [
        (svc.CHECKBOX, True, True),
        (svc.PASS_FAIL_NA, "fail", "fail"),
        (svc.TEXT, "  hello  ", "hello"),
        (svc.NUMERIC, 12.5, 12.5),
        (svc.SELECTION, "a", "a"),
    ],
)
def test_validate_and_normalize_response_accepts_valid_values(item_type, value, expected) -> None:
    item = _item(item_type=item_type, options=[{"id": "a", "label": "A"}])
    normalized_value, na = svc.validate_and_normalize_response(item, value, False)
    assert normalized_value == expected
    assert na is False


def test_na_rejected_when_not_allowed() -> None:
    item = _item(na_allowed=False)
    with pytest.raises(svc.ChecklistValidationError):
        svc.validate_and_normalize_response(item, None, True)


def test_na_allowed_returns_null_value() -> None:
    item = _item(na_allowed=True)
    value, na = svc.validate_and_normalize_response(item, "ignored", True)
    assert value is None
    assert na is True


def test_numeric_bounds_enforced() -> None:
    item = _item(item_type=svc.NUMERIC, min_value=0, max_value=10)
    with pytest.raises(svc.ChecklistValidationError):
        svc.validate_and_normalize_response(item, 11, False)
    value, _na = svc.validate_and_normalize_response(item, 5.5, False)
    assert value == 5.5


def test_required_text_rejects_blank() -> None:
    item = _item(item_type=svc.TEXT, required=True)
    with pytest.raises(svc.ChecklistValidationError):
        svc.validate_and_normalize_response(item, "   ", False)


def test_selection_rejects_value_outside_options() -> None:
    item = _item(item_type=svc.SELECTION, options=[{"id": "a", "label": "A"}])
    with pytest.raises(svc.ChecklistValidationError):
        svc.validate_and_normalize_response(item, "b", False)


def test_record_response_appends_history_without_losing_prior_entries() -> None:
    item = _item()
    first = svc.record_response(item, True, False, "", actor_id=101)
    second = svc.record_response(item, False, False, "changed my mind", actor_id=202)

    assert item["history"] == [first, second]
    assert item["response"] == second
    assert first["recorded_by"] == 101
    assert second["recorded_by"] == 202


def test_is_answered_and_is_failed() -> None:
    answered = _item(response={"value": "fail", "na": False}, item_type=svc.PASS_FAIL_NA)
    assert svc.is_answered(answered)
    assert svc.is_failed(answered)

    na_item = _item(response={"value": None, "na": True}, item_type=svc.PASS_FAIL_NA)
    assert svc.is_answered(na_item)
    assert not svc.is_failed(na_item)

    unanswered = _item()
    assert not svc.is_answered(unanswered)
    assert not svc.is_failed(unanswered)


def test_compute_progress() -> None:
    sections = [
        {
            "id": "s1",
            "name": "A",
            "items": [
                _item(id="i1", required=True, response={"value": True, "na": False}),
                _item(id="i2", required=True, response=None),
                _item(
                    id="i3",
                    item_type=svc.PASS_FAIL_NA,
                    response={"value": "fail", "na": False},
                ),
                _item(id="i4", response={"value": None, "na": True}),
            ],
        }
    ]
    progress = svc.compute_progress(sections)
    assert progress["total_items"] == 4
    assert progress["answered_items"] == 3
    assert progress["unanswered_required_items"] == ["i2"]
    assert progress["na_items"] == 1
    assert progress["failed_items"] == ["i3"]
    assert progress["completion_percentage"] == 75.0


def test_compute_progress_empty_checklist() -> None:
    progress = svc.compute_progress([])
    assert progress["total_items"] == 0
    assert progress["completion_percentage"] == 0.0


@pytest.mark.parametrize(
    "current,target,allowed",
    [
        (svc.NOT_STARTED, svc.IN_PROGRESS, True),
        (svc.NOT_STARTED, svc.COMPLETED, False),
        (svc.IN_PROGRESS, svc.COMPLETED, True),
        (svc.COMPLETED, svc.IN_PROGRESS, True),
        (svc.ARCHIVED, svc.IN_PROGRESS, False),
        (svc.ARCHIVED, svc.NOT_STARTED, False),
    ],
)
def test_status_transition_boundaries(current, target, allowed) -> None:
    if allowed:
        svc.apply_status_transition(current, target)
    else:
        with pytest.raises(svc.ChecklistValidationError):
            svc.apply_status_transition(current, target)


def test_status_after_first_response() -> None:
    assert svc.status_after_first_response(svc.NOT_STARTED) == svc.IN_PROGRESS
    assert svc.status_after_first_response(svc.COMPLETED) == svc.COMPLETED
