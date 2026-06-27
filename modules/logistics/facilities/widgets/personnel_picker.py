from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt, QStringListModel, QTimer, Signal
from PySide6.QtWidgets import QCompleter, QHBoxLayout, QLineEdit, QWidget

from utils.api_client import api_client


class PersonnelPicker(QWidget):
    personnelSelected = Signal(object, str)
    textChanged = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._personnel_id: str = ""
        self._results: list[dict[str, Any]] = []
        self._display_to_result: dict[str, dict[str, Any]] = {}

        self.line_edit = QLineEdit(self)
        self.line_edit.setPlaceholderText("Search or enter manager...")

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

    @property
    def personnel_id(self) -> str:
        return self._personnel_id

    @property
    def personnel_text(self) -> str:
        return self.line_edit.text().strip()

    def set_value(self, personnel_id: str, personnel_text: str) -> None:
        self._personnel_id = str(personnel_id or "")
        self.line_edit.blockSignals(True)
        self.line_edit.setText(personnel_text or "")
        self.line_edit.blockSignals(False)

    def clear(self) -> None:  # type: ignore[override]
        self._personnel_id = ""
        self.line_edit.clear()

    def _on_text_changed(self, text: str) -> None:
        self._personnel_id = ""
        self.textChanged.emit(text)
        self._timer.start()

    def _refresh_results(self) -> None:
        query = self.line_edit.text().strip()
        try:
            self._results = (
                api_client.get("/api/master/personnel", params={"search": query, "limit": 25}) or []
            )
        except Exception:
            self._results = []
        self._display_to_result.clear()
        values: list[str] = []
        for result in self._results[:25]:
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
            self._personnel_id = ""
            self.line_edit.blockSignals(True)
            self.line_edit.setText(text)
            self.line_edit.blockSignals(False)
            self.personnelSelected.emit("", text)
            return
        self._personnel_id = str(result.get("id") or "")
        name = str(result.get("name") or "")
        self.line_edit.blockSignals(True)
        self.line_edit.setText(name)
        self.line_edit.blockSignals(False)
        self.personnelSelected.emit(self._personnel_id, name)

    @staticmethod
    def _format_result(result: dict[str, Any]) -> str:
        context = " • ".join(
            value
            for value in [
                str(result.get("callsign") or ""),
                str(result.get("primary_role") or ""),
                str(result.get("home_unit") or ""),
            ]
            if value
        )
        name = str(result.get("name") or "")
        return f"{name} — {context}" if context else name


__all__ = ["PersonnelPicker"]
