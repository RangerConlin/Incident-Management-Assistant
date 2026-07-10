"""Multi-select picker dialog for linking a hazard to work assignments, teams, and tasks."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTabWidget, QVBoxLayout, QWidget

from utils.api_client import api_client

from .checkable_list import CheckableList


def _fetch_work_assignments(incident_id: str) -> list[dict[str, Any]]:
    return api_client.get(f"/api/incidents/{incident_id}/planning/work-assignments") or []


def _fetch_teams(incident_id: str) -> list[dict[str, Any]]:
    return api_client.get(f"/api/incidents/{incident_id}/operations/teams") or []


def _fetch_tasks(incident_id: str) -> list[dict[str, Any]]:
    return api_client.get(f"/api/incidents/{incident_id}/operations/tasks") or []


class LinkPickerDialog(QDialog):
    """Modal dialog for selecting linked work assignments, teams, and tasks."""

    def __init__(
        self,
        incident_id: str,
        *,
        work_assignment_ids: Optional[list[int]] = None,
        team_ids: Optional[list[int]] = None,
        task_ids: Optional[list[int]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Link Hazard To…")
        self.setModal(True)
        self.resize(480, 420)

        tabs = QTabWidget(self)

        self._wa_list = CheckableList(
            _fetch_work_assignments(incident_id),
            "id",
            lambda d: f"{d.get('assignment_number', '')} — {d.get('assignment_name', '')}",
            set(work_assignment_ids or []),
        )
        tabs.addTab(self._wa_list, "Work Assignments")

        self._team_list = CheckableList(
            _fetch_teams(incident_id),
            "int_id",
            lambda d: f"{d.get('name', '')} ({d.get('callsign') or '—'})",
            set(team_ids or []),
        )
        tabs.addTab(self._team_list, "Teams")

        self._task_list = CheckableList(
            _fetch_tasks(incident_id),
            "int_id",
            lambda d: f"{d.get('task_id', '')} — {d.get('title', '')}",
            set(task_ids or []),
        )
        tabs.addTab(self._task_list, "Tasks")

        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(button_box)

    def selected_links(self) -> dict[str, list[int]]:
        return {
            "work_assignment_ids": self._wa_list.selected_ids(),
            "team_ids": self._team_list.selected_ids(),
            "task_ids": self._task_list.selected_ids(),
        }
