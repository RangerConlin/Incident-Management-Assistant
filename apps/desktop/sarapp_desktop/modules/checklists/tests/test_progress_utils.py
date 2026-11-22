from __future__ import annotations

from modules.checklists.progress_utils import progress_text, summarize


def _item(**overrides):
    base = {"id": "i1", "item_type": "checkbox", "label": "Item", "required": False, "response": None}
    base.update(overrides)
    return base


def test_summarize_excludes_na_from_applicable() -> None:
    sections = [
        {
            "id": "s1",
            "items": [
                _item(id="i1", response={"value": True, "na": False}),
                _item(id="i2", response={"value": None, "na": True}),
                _item(id="i3", required=True, response=None),
                _item(
                    id="i4",
                    item_type="pass_fail_na",
                    response={"value": "fail", "na": False},
                ),
            ],
        }
    ]
    summary = summarize(sections)
    assert summary["total_items"] == 4
    assert summary["na_items"] == 1
    assert summary["applicable_items"] == 3
    assert summary["answered_applicable_items"] == 2
    assert summary["unanswered_required"] == ["i3"]
    assert summary["failed_items"] == [{"item_id": "i4", "label": "Item"}]


def test_progress_text() -> None:
    sections = [{"id": "s1", "items": [_item(id="i1", response={"value": True, "na": False})]}]
    assert progress_text(sections) == "1/1"


def test_empty_checklist() -> None:
    summary = summarize([])
    assert summary["total_items"] == 0
    assert progress_text([]) == "0/0"
