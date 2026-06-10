import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from modules.admin.resource_types.data import ResourceAssignmentRepository
from modules.operations.teams.panels.team_detail_window import TeamDetailWindow


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_team_detail_window_populates_empty_resource_type(qt_app: QApplication) -> None:
    window = TeamDetailWindow()
    try:
        assert isinstance(window._resource_assignments, ResourceAssignmentRepository)

        window._populate_resource_type_selection({"resource_type_id": None})

        assert window._resource_type_search.resource_type_id is None
        assert window._resource_type_search.resource_type_text == ""
    finally:
        window.close()
