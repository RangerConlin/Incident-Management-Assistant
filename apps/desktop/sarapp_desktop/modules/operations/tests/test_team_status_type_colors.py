from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem

from modules.operations.panels.team_status_panel import TeamStatusPanel
from utils import styles


class _PanelStyleHarness:
    _apply_team_type_color = TeamStatusPanel._apply_team_type_color

    def __init__(self, definition: dict) -> None:
        self.table = QTableWidget(1, 4)
        self.table.setItem(0, 3, QTableWidgetItem("GT"))
        self._team_type_styles = {"GT": definition}


def test_team_type_cell_uses_independent_catalog_text_color(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    assert app is not None
    monkeypatch.setattr(
        styles,
        "TEAM_TYPE_COLORS",
        {"team_type_search_rescue": QColor("#228b22")},
    )
    harness = _PanelStyleHarness(
        {
            "color_key": "team_type_search_rescue",
            "text_color_key": "team_text_white",
        }
    )

    harness._apply_team_type_color(0, "GT")

    item = harness.table.item(0, 3)
    assert item.background().color() == QColor("#228b22").lighter(130)
    assert item.foreground().color() == styles.team_type_text_colors()["team_text_white"]
