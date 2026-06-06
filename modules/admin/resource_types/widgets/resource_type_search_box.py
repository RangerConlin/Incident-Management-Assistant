"""Reusable smart search widget for selecting or entering resource types."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QStringListModel, QTimer, Signal
from PySide6.QtWidgets import QCompleter, QHBoxLayout, QLineEdit, QWidget

from ..data.resource_type_repository import ResourceTypeRepository
from ..models.resource_type_models import ResourceTypeSearchResult


class ResourceTypeSearchBox(QWidget):
    """One-box resource type lookup with free-text fallback.

    Store both values from this widget:
    - ``resource_type_id`` identifies a library record when the user selected one.
    - ``resource_type_text`` preserves exactly what the user typed when no record
      exists or when free text is appropriate for the workflow.
    """

    resourceTypeSelected = Signal(object, str)
    textChanged = Signal(str)

    def __init__(
        self,
        repository: Optional[ResourceTypeRepository] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository or ResourceTypeRepository()
        self._resource_type_id: Optional[int] = None
        self._results: list[ResourceTypeSearchResult] = []
        self._display_to_result: dict[str, ResourceTypeSearchResult] = {}

        self.line_edit = QLineEdit(self)
        self.line_edit.setPlaceholderText("Search or enter resource type...")

        self._model = QStringListModel(self)
        self._completer = QCompleter(self._model, self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self.line_edit.setCompleter(self._completer)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.line_edit)

        # Debouncing avoids querying SQLite on every keystroke while the user is
        # still typing, which keeps the widget responsive in large catalogs.
        self._timer = QTimer(self)
        self._timer.setInterval(150)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._refresh_results)

        self.line_edit.textChanged.connect(self._on_text_changed)
        self._completer.activated[str].connect(self._on_completion_selected)

    @property
    def resource_type_id(self) -> Optional[int]:
        """Selected resource type ID, or ``None`` for free-text entries."""

        return self._resource_type_id

    @property
    def resource_type_text(self) -> str:
        """The selected display text or user-entered free text."""

        return self.line_edit.text().strip()

    def set_value(self, resource_type_id: Optional[int], resource_type_text: str) -> None:
        """Set the widget value from a stored ID/text pair."""

        self._resource_type_id = resource_type_id
        self.line_edit.setText(resource_type_text or "")

    def clear(self) -> None:  # type: ignore[override]
        self._resource_type_id = None
        self.line_edit.clear()

    def _on_text_changed(self, text: str) -> None:
        # Typing means the previous selected ID may no longer match the visible
        # text, so clear it until the user picks another completion.
        self._resource_type_id = None
        self.textChanged.emit(text)
        self._timer.start()

    def _refresh_results(self) -> None:
        query = self.line_edit.text().strip()
        self._results = self.repository.search_resource_types(query) if query else []
        display_values: list[str] = []
        self._display_to_result.clear()
        for result in self._results:
            label = self._format_result(result)
            display_values.append(label)
            self._display_to_result[label] = result
        if query and not self._results:
            display_values.append(f"Use free text: {query}")
        self._model.setStringList(display_values)
        if display_values:
            self._completer.complete()

    def _on_completion_selected(self, display_text: str) -> None:
        result = self._display_to_result.get(display_text)
        if result is None:
            # Free-text completion: keep ID empty and strip helper text.
            text = display_text.removeprefix("Use free text: ").strip()
            self._resource_type_id = None
            self.line_edit.blockSignals(True)
            self.line_edit.setText(text)
            self.line_edit.blockSignals(False)
            self.resourceTypeSelected.emit(None, text)
            return
        self.line_edit.blockSignals(True)
        self.line_edit.setText(result.resource_type_text)
        self.line_edit.blockSignals(False)
        self._resource_type_id = result.resource_type_id
        self.resourceTypeSelected.emit(result.resource_type_id, result.resource_type_text)

    @staticmethod
    def _format_result(result: ResourceTypeSearchResult) -> str:
        # Example: "Radio Cache — Equipment Kit / Cache • AHJ Custom".
        context = " • ".join(value for value in (result.category, result.source) if value)
        if result.matched_on and result.matched_on not in {"name", "display name"}:
            context = f"{context} • matched {result.matched_on}" if context else f"matched {result.matched_on}"
        return f"{result.resource_type_text} — {context}" if context else result.resource_type_text
