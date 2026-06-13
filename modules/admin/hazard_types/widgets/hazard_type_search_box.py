"""Reusable smart search widget for selecting or entering hazard types."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QStringListModel, QTimer, Signal
from PySide6.QtWidgets import QCompleter, QHBoxLayout, QLineEdit, QWidget

from ..data.hazard_type_repository import ApiHazardTypeRepository, HazardTypeRepository
from ..models.hazard_type_models import HazardTypeSearchResult


class HazardTypeSearchBox(QWidget):
    """One-box hazard lookup with free-text fallback."""

    hazardTypeSelected = Signal(object, str)
    textChanged = Signal(str)

    def __init__(
        self,
        repository: Optional[HazardTypeRepository] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository or ApiHazardTypeRepository()
        self._hazard_type_id: Optional[int] = None
        self._results: list[HazardTypeSearchResult] = []
        self._display_to_result: dict[str, HazardTypeSearchResult] = {}

        self.line_edit = QLineEdit(self)
        self.line_edit.setPlaceholderText("Search or enter hazard type...")

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
    def hazard_type_id(self) -> Optional[int]:
        return self._hazard_type_id

    @property
    def hazard_type_text(self) -> str:
        return self.line_edit.text().strip()

    def set_value(self, hazard_type_id: Optional[int], hazard_type_text: str) -> None:
        self._hazard_type_id = hazard_type_id
        self.line_edit.blockSignals(True)
        self.line_edit.setText(hazard_type_text or "")
        self.line_edit.blockSignals(False)

    def clear(self) -> None:  # type: ignore[override]
        self._hazard_type_id = None
        self.line_edit.clear()

    def _on_text_changed(self, text: str) -> None:
        self._hazard_type_id = None
        self.textChanged.emit(text)
        self._timer.start()

    def _refresh_results(self) -> None:
        query = self.line_edit.text().strip()
        self._results = self.repository.search_hazard_types(query) if query else []
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
            text = display_text.removeprefix("Use free text: ").strip()
            self._hazard_type_id = None
            self.line_edit.blockSignals(True)
            self.line_edit.setText(text)
            self.line_edit.blockSignals(False)
            self.hazardTypeSelected.emit(None, text)
            return
        self.line_edit.blockSignals(True)
        self.line_edit.setText(result.hazard_type_text)
        self.line_edit.blockSignals(False)
        self._hazard_type_id = result.hazard_type_id
        self.hazardTypeSelected.emit(result.hazard_type_id, result.hazard_type_text)

    @staticmethod
    def _format_result(result: HazardTypeSearchResult) -> str:
        context = " • ".join(
            value for value in (result.category, result.default_risk_level) if value
        )
        if result.matched_on and result.matched_on not in {"name", "display name"}:
            context = f"{context} • matched {result.matched_on}" if context else f"matched {result.matched_on}"
        return f"{result.hazard_type_text} — {context}" if context else result.hazard_type_text
