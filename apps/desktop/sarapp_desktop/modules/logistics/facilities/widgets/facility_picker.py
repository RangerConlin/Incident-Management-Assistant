from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QStringListModel, QTimer, Signal
from PySide6.QtWidgets import QCompleter, QHBoxLayout, QLineEdit, QWidget

from ..models import FacilityRecord
from ..service import FacilitiesService


class FacilityPicker(QWidget):
    facilitySelected = Signal(object, str)
    textChanged = Signal(str)

    def __init__(
        self,
        service: Optional[FacilitiesService] = None,
        facility_type: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.service = service or FacilitiesService()
        self.facility_type = facility_type
        self._facility_id: str = ""
        self._results: list[FacilityRecord] = []
        self._display_to_result: dict[str, FacilityRecord] = {}

        self.line_edit = QLineEdit(self)
        self.line_edit.setPlaceholderText("Search or enter facility...")

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
    def facility_id(self) -> str:
        return self._facility_id

    @property
    def facility_text(self) -> str:
        return self.line_edit.text().strip()

    def set_value(self, facility_id: str, facility_text: str) -> None:
        self._facility_id = str(facility_id or "")
        self.line_edit.blockSignals(True)
        self.line_edit.setText(facility_text or "")
        self.line_edit.blockSignals(False)

    def clear(self) -> None:  # type: ignore[override]
        self._facility_id = ""
        self.line_edit.clear()

    def _on_text_changed(self, text: str) -> None:
        self._facility_id = ""
        self.textChanged.emit(text)
        self._timer.start()

    def _refresh_results(self) -> None:
        query = self.line_edit.text().strip()
        self._results = self.service.list_facilities(
            facility_type=self.facility_type,
            text_search=query,
        ) if query else self.service.list_facilities(facility_type=self.facility_type)
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
            self._facility_id = ""
            self.line_edit.blockSignals(True)
            self.line_edit.setText(text)
            self.line_edit.blockSignals(False)
            self.facilitySelected.emit("", text)
            return
        self._facility_id = result.id
        self.line_edit.blockSignals(True)
        self.line_edit.setText(result.name)
        self.line_edit.blockSignals(False)
        self.facilitySelected.emit(result.id, result.name)

    @staticmethod
    def _format_result(result: FacilityRecord) -> str:
        context = " • ".join(value for value in [result.facility_type, result.status, result.address] if value)
        return f"{result.name} — {context}" if context else result.name


__all__ = ["FacilityPicker"]
