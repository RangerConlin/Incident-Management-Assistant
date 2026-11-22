from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

import modules.checklists.api as api
from modules.checklists.widgets.new_checklist_dialog import NewChecklistDialog


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _suppress_message_boxes(monkeypatch) -> None:
    # QMessageBox.warning()/.information() open a real modal event loop —
    # in a headless test with no one to click them, that blocks forever.
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))


_TEMPLATES = [
    {"id": 1, "name": "Vehicle Inspection", "category": "Logistics", "description": "Pre-trip", "sections": [{"id": "s1", "items": [{"id": "i1"}, {"id": "i2"}]}]},
    {"id": 2, "name": "Radio Check", "category": "Communications", "description": "", "sections": []},
]


def test_template_tab_lists_and_filters_by_search(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(api, "list_templates", lambda **kw: _TEMPLATES)
    monkeypatch.setattr(api, "list_template_categories", lambda: ["Logistics", "Communications"])

    dialog = NewChecklistDialog("INC1")
    assert dialog.template_list.count() == 2

    dialog.template_search_edit.setText("vehicle")
    assert dialog.template_list.count() == 1
    assert "Vehicle Inspection" in dialog.template_list.item(0).text()
    assert "2 items" in dialog.template_list.item(0).text()


def test_template_tab_filters_by_category(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(api, "list_templates", lambda **kw: _TEMPLATES)
    monkeypatch.setattr(api, "list_template_categories", lambda: ["Logistics", "Communications"])

    dialog = NewChecklistDialog("INC1")
    dialog.template_category_combo.setCurrentText("Communications")
    assert dialog.template_list.count() == 1
    assert "Radio Check" in dialog.template_list.item(0).text()


def test_blank_checklist_requires_at_least_one_item(monkeypatch) -> None:
    _app()
    _suppress_message_boxes(monkeypatch)
    monkeypatch.setattr(api, "list_templates", lambda **kw: [])
    monkeypatch.setattr(api, "list_template_categories", lambda: [])

    dialog = NewChecklistDialog("INC1")
    dialog.name_edit.setText("Blank Checklist")
    dialog.tabs.setCurrentIndex(1)
    assert dialog._build_blank_sections() is None  # no rows added yet


def test_blank_checklist_builds_sections_from_rows(monkeypatch) -> None:
    _app()
    _suppress_message_boxes(monkeypatch)
    monkeypatch.setattr(api, "list_templates", lambda **kw: [])
    monkeypatch.setattr(api, "list_template_categories", lambda: [])

    dialog = NewChecklistDialog("INC1")
    dialog.tabs.setCurrentIndex(1)
    dialog._add_item_row()
    dialog.item_table.item(0, 0).setText("Equipment")
    dialog.item_table.item(0, 1).setText("Checked")
    dialog.item_table.item(0, 5).setText("")

    sections = dialog._build_blank_sections()
    assert sections is not None
    assert sections[0]["name"] == "Equipment"
    assert sections[0]["items"][0]["item_type"] == "checkbox"
    assert sections[0]["items"][0]["label"] == "Checked"


def test_blank_checklist_selection_item_parses_options(monkeypatch) -> None:
    _app()
    _suppress_message_boxes(monkeypatch)
    monkeypatch.setattr(api, "list_templates", lambda **kw: [])
    monkeypatch.setattr(api, "list_template_categories", lambda: [])

    dialog = NewChecklistDialog("INC1")
    dialog.tabs.setCurrentIndex(1)
    dialog._add_item_row()
    dialog.item_table.item(0, 1).setText("Condition")
    dialog.item_table.cellWidget(0, 2).setCurrentIndex(
        [dialog.item_table.cellWidget(0, 2).itemData(i) for i in range(dialog.item_table.cellWidget(0, 2).count())].index("selection")
    )
    dialog.item_table.item(0, 5).setText("Good, Fair, Poor")

    sections = dialog._build_blank_sections()
    assert sections is not None
    options = sections[0]["items"][0]["options"]
    assert [o["label"] for o in options] == ["Good", "Fair", "Poor"]
