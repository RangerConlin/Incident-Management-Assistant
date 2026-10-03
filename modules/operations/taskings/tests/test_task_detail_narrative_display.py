import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QApplication, QComboBox

from modules.operations.taskings import task_detail_widget as widget
from bridge.incident_bridge import IncidentBridge
from utils.incident_cache import incident_cache


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_yes_no_delegate_keeps_display_text_human_readable() -> None:
    _app()
    model = QStandardItemModel(1, 1)
    item = QStandardItem("No")
    item.setData("No", Qt.DisplayRole)
    item.setData("No", Qt.EditRole)
    item.setData(0, Qt.UserRole)
    model.setItem(0, 0, item)
    index = model.index(0, 0)

    editor = QComboBox()
    editor.addItems(["No", "Yes"])
    editor.setCurrentIndex(1)

    delegate = widget._YesNoDelegate()
    delegate.setModelData(editor, model, index)

    assert model.data(index, Qt.DisplayRole) == "Yes"
    assert model.data(index, Qt.EditRole) == "Yes"
    assert model.data(index, Qt.UserRole) == 1


def test_yes_no_delegate_update_allows_immediate_row_highlight() -> None:
    _app()
    instance = widget.TaskDetailWindow.__new__(widget.TaskDetailWindow)
    instance._nar_model = QStandardItemModel(1, 7)
    for column in range(instance._nar_model.columnCount()):
        instance._nar_model.setItem(0, column, QStandardItem(""))

    critical_item = instance._nar_model.item(0, 5)
    critical_item.setData("No", Qt.DisplayRole)
    critical_item.setData("No", Qt.EditRole)
    critical_item.setData(0, Qt.UserRole)
    index = instance._nar_model.index(0, 5)

    editor = QComboBox()
    editor.addItems(["No", "Yes"])
    editor.setCurrentIndex(1)
    widget._YesNoDelegate().setModelData(editor, instance._nar_model, index)
    instance._apply_row_critical_highlight(0)

    assert instance._is_row_critical(0) is True
    for column in range(instance._nar_model.columnCount()):
        assert instance._nar_model.item(0, column).data(Qt.BackgroundRole) is not None


def test_resolve_person_display_uses_canonical_person_record(monkeypatch) -> None:
    def _missing_person(_value):
        return None

    monkeypatch.setattr(
        "modules.logistics.checkin.repository.get_person_identity",
        _missing_person,
    )

    class _Api:
        def get(self, path):
            assert path == "/api/auth/users"
            return [{"user_id": "42", "person_record": 42, "display_name": "Alex Morgan"}]

    monkeypatch.setattr("utils.api_client.api_client", _Api())

    assert widget._resolve_person_display("42") == "Alex Morgan"


def test_unresolved_numeric_person_id_is_not_displayed(monkeypatch) -> None:
    monkeypatch.setattr(
        "modules.logistics.checkin.repository.get_person_identity",
        lambda _value: None,
    )
    monkeypatch.setattr("utils.api_client.api_client.get", lambda _path: [])

    assert widget._resolve_person_display("405021") == ""


def test_narrative_position_display_resolves_numeric_position_id(monkeypatch) -> None:
    _app()
    instance = widget.TaskDetailWindow.__new__(widget.TaskDetailWindow)
    monkeypatch.setattr(instance, "_position_title_for_id", lambda value: "Operations Section Chief")

    assert instance._narrative_position_display({"team_num": "2"}) == "Operations Section Chief"


def test_narrative_bridge_uses_cache_and_resolves_author_without_api(monkeypatch) -> None:
    monkeypatch.setattr(
        "utils.incident_context.get_active_incident_id",
        lambda: "INC-NARRATIVE-CACHE",
    )
    monkeypatch.setattr(
        "utils.api_client.api_client.get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("cached narrative must not call the API")
        ),
    )
    incident_cache.load_snapshot(
        "INC-NARRATIVE-CACHE",
        {
            "tasks": [
                {
                    "_id": "task-1",
                    "int_id": 1,
                    "narrative": [
                        {
                            "id": "entry-1",
                            "timestamp": "2026-10-03T11:00:00+00:00",
                            "narrative": "Search started.",
                            "entered_by": "42",
                        }
                    ],
                }
            ],
            "incident_personnel": [
                {"_id": "person-42", "person_record": 42, "name": "Alex Morgan"}
            ],
        },
    )
    try:
        rows = IncidentBridge().listTaskNarrative(1, "", False, "")
    finally:
        incident_cache.clear()

    assert rows[0]["entered_by_display"] == "Alex Morgan"


def test_local_only_person_display_does_not_use_network(monkeypatch) -> None:
    monkeypatch.setattr(
        "modules.logistics.checkin.repository.get_person_identity",
        lambda _value: (_ for _ in ()).throw(AssertionError("network fallback used")),
    )
    monkeypatch.setattr(
        "utils.api_client.api_client.get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network fallback used")),
    )

    assert widget._resolve_person_display("404", allow_network=False) == ""
