"""Incident-scoped Team search/select control.

Mirrors `modules.logistics.facilities.widgets.personnel_picker.PersonnelPicker`'s
search-as-you-type shape, since no reusable Team picker exists yet
elsewhere in the desktop app (checked before writing this — see the Phase
1D audit notes). Teams' own search endpoint
(`/operations/teams/search`) only matches a label or callsign exactly, so
this filters the incident's team list client-side instead, same as this
module's own GIS-feature and Meeting pickers.
"""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt, QStringListModel, QTimer, Signal
from PySide6.QtWidgets import QCompleter, QHBoxLayout, QLineEdit, QWidget

from ..record_resolvers import list_teams


class TeamPicker(QWidget):
    teamSelected = Signal(object, str)
    textChanged = Signal(str)

    def __init__(self, incident_id: str | None = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.incident_id = incident_id
        self._team_id: str = ""
        self._results: list[dict[str, Any]] = []
        self._display_to_result: dict[str, dict[str, Any]] = {}

        self.line_edit = QLineEdit(self)
        self.line_edit.setPlaceholderText("Search or enter team...")

        self._model = QStringListModel(self)
        self._completer = QCompleter(self._model, self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self.line_edit.setCompleter(self._completer)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.line_edit)

        self._timer = QTimer(self)
        self._timer.setInterval(150)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._refresh_results)

        self.line_edit.textChanged.connect(self._on_text_changed)
        self._completer.activated[str].connect(self._on_completion_selected)

    def set_incident_id(self, incident_id: str | None) -> None:
        self.incident_id = incident_id

    @property
    def team_id(self) -> str:
        return self._team_id

    @property
    def team_text(self) -> str:
        return self.line_edit.text().strip()

    def set_value(self, team_id: str, team_text: str) -> None:
        self._team_id = str(team_id or "")
        self.line_edit.blockSignals(True)
        self.line_edit.setText(team_text or "")
        self.line_edit.blockSignals(False)

    def clear(self) -> None:  # type: ignore[override]
        self._team_id = ""
        self.line_edit.clear()

    def _on_text_changed(self, text: str) -> None:
        self._team_id = ""
        self.textChanged.emit(text)
        self._timer.start()

    def _refresh_results(self) -> None:
        query = self.line_edit.text().strip().lower()
        if not self.incident_id:
            self._results = []
        else:
            all_teams = list_teams(self.incident_id)
            self._results = [
                team for team in all_teams
                if not query or query in str(team.get("name") or "").lower() or query in str(team.get("callsign") or "").lower()
            ][:25]
        self._display_to_result.clear()
        values: list[str] = []
        for result in self._results:
            label = self._format_result(result)
            values.append(label)
            self._display_to_result[label] = result
        if query and not self._results:
            values.append(f"Use free text: {query}")
        self._model.setStringList(values)
        if values:
            self._completer.complete()

    def _on_completion_selected(self, display_text: str) -> None:
        result = self._display_to_result.get(display_text)
        if result is None:
            text = display_text.removeprefix("Use free text: ").strip()
            self._team_id = ""
            self.line_edit.blockSignals(True)
            self.line_edit.setText(text)
            self.line_edit.blockSignals(False)
            self.teamSelected.emit("", text)
            return
        self._team_id = str(result.get("int_id") or "")
        name = str(result.get("name") or "")
        self.line_edit.blockSignals(True)
        self.line_edit.setText(name)
        self.line_edit.blockSignals(False)
        self.teamSelected.emit(self._team_id, name)

    @staticmethod
    def _format_result(result: dict[str, Any]) -> str:
        context = " • ".join(
            value
            for value in [str(result.get("callsign") or ""), str(result.get("status") or "")]
            if value
        )
        name = str(result.get("name") or "")
        return f"{name} ({context})" if context else name
