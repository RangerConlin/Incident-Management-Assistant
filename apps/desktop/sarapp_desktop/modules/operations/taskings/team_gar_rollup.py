"""
TeamGarRollupPanel
====================
Read-only roll-up of each team assigned to a Task, showing that team's
current GAR (Green-Amber-Red) band and score.

GAR is scored per team, not per task (see
``modules/operations/teams/panels/gar_editor.py``), so a task with multiple
teams can show multiple GAR scores here. Editing happens on the Team, not
here — each row links out to that team's own Safety tab.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from utils.styles import get_palette, subscribe_theme

_BAND_PALETTE_TOKEN = {
    "Green": "success",
    "Amber": "warning",
    "Red": "danger",
}


def _band_color_hex(band: str) -> str:
    token = _BAND_PALETTE_TOKEN.get(band, "ctrl_border")
    return get_palette().get(token, get_palette().get("ctrl_border")).name()


class TeamGarRollupPanel(QWidget):
    """Shows each task-assigned team's current GAR band/score, read-only."""

    def __init__(self, task_id: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._task_id = int(task_id)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)

        header = QLabel("Team GAR Status", self)
        header.setStyleSheet("font-weight: 600; font-size: 14px;")
        self._layout.addWidget(header)

        self._rows_container = QWidget(self)
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(6)
        self._layout.addWidget(self._rows_container)

        self._empty_label = QLabel("No teams assigned to this task yet.", self)
        self._empty_label.setWordWrap(True)
        self._layout.addWidget(self._empty_label)
        self._empty_label.setVisible(False)

        try:
            subscribe_theme(self, lambda _name: self.reload())
        except Exception:
            pass

    def reload(self) -> None:
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        from modules.operations.taskings.repository import list_task_teams
        from modules.operations.teams.data.repository import get_team_gar
        from modules.operations.teams.data.gar import GarAssessment

        try:
            teams = list_task_teams(self._task_id) or []
        except Exception:
            teams = []

        self._empty_label.setVisible(not teams)
        for team in teams:
            team_id = getattr(team, "team_id", None)
            team_name = getattr(team, "team_name", None) or f"Team {team_id}"
            current = None
            if team_id is not None:
                try:
                    payload = get_team_gar(int(team_id))
                    raw = payload.get("current")
                    current = GarAssessment.from_dict(raw) if raw else None
                except Exception:
                    current = None
            self._rows_layout.addWidget(self._build_row(team_id, team_name, current))

    def _build_row(self, team_id: Optional[int], team_name: str, current) -> QFrame:
        row = QFrame(self._rows_container)
        row.setFrameShape(QFrame.StyledPanel)
        row.setAttribute(Qt.WA_StyledBackground, True)
        band = current.band if current else None
        color = _band_color_hex(band) if band else get_palette().get("ctrl_border").name()
        row.setStyleSheet(
            "QFrame { "
            f"border:1px solid {get_palette().get('ctrl_border').name()}; "
            f"border-left:4px solid {color}; "
            "border-radius:6px; "
            "}"
        )
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 8, 12, 8)

        name_label = QLabel(team_name, row)
        name_label.setStyleSheet("font-weight: 700;")
        layout.addWidget(name_label)

        if current:
            status_label = QLabel(f"{current.band} — Score {current.score}", row)
        else:
            status_label = QLabel("Not yet assessed", row)
        layout.addWidget(status_label)
        layout.addStretch(1)

        view_btn = QPushButton("View Team", row)
        if team_id is not None:
            view_btn.clicked.connect(lambda _checked=False, tid=int(team_id): self._open_team(tid))
        else:
            view_btn.setEnabled(False)
        layout.addWidget(view_btn)
        return row

    def _open_team(self, team_id: int) -> None:
        try:
            from modules.operations.teams.windows import open_team_detail_window

            open_team_detail_window(team_id)
        except Exception:
            pass
