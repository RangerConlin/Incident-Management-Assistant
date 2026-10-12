from __future__ import annotations

import os

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from modules.projection_dashboard.windows import TeamBoard


@pytest.fixture()
def qt_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_team_board_initializes_with_saved_widths(qt_app: QApplication) -> None:
    # Must match the explicitly-scoped QSettings("SARApp", "ProjectionDashboard")
    # the widget itself uses (see windows.py's _settings() helper) — a bare
    # QSettings() here would write somewhere the widget never reads from.
    QSettings("SARApp", "ProjectionDashboard").setValue(
        "projection_dashboard/ProjectionTeamBoard/column_widths",
        [180, 190, 200, 210, 220],
    )

    board = TeamBoard()

    assert board.table.columnWidth(0) == 180
    assert board.table.columnWidth(1) == 190
