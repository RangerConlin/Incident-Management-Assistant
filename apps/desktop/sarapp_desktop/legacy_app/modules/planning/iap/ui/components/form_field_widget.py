"""Reusable widgets that render individual form fields."""

from __future__ import annotations

from typing import Any

from PySide6 import QtCore, QtWidgets


class FormFieldWidget(QtWidgets.QWidget):
    """Simple representation of a form field used by the generic editor."""

    valueChanged = QtCore.Signal(str, object)

    def __init__(
        self,
        field_id: str,
        label: str,
        value: Any | None = None,
        multiline: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.field_id = field_id
        self._multiline = multiline
        self._label = QtWidgets.QLabel(label)
        self._label.setObjectName("form-field-label")
        self._label.setWordWrap(True)
        self._input = self._create_editor(multiline)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)
        layout.addWidget(self._input)
        self.setValue(value)

    # ------------------------------------------------------------------ internals
    def _create_editor(self, multiline: bool) -> QtWidgets.QWidget:
        if multiline:
            editor = QtWidgets.QPlainTextEdit(self)
            editor.textChanged.connect(self._on_text_changed)
            return editor
        editor = QtWidgets.QLineEdit(self)
        editor.textChanged.connect(self._on_line_changed)
        return editor

    def _on_text_changed(self) -> None:
        widget: QtWidgets.QPlainTextEdit = self._input  # type: ignore[assignment]
        self.valueChanged.emit(self.field_id, widget.toPlainText())

    def _on_line_changed(self, text: str) -> None:
        self.valueChanged.emit(self.field_id, text)

    # --------------------------------------------------------------------- helpers
    def setValue(self, value: Any | None) -> None:  # noqa: N802 - Qt slot style
        """Populate the editor with ``value``."""

        if self._multiline:
            widget: QtWidgets.QPlainTextEdit = self._input  # type: ignore[assignment]
            widget.blockSignals(True)
            widget.setPlainText("" if value is None else str(value))
            widget.blockSignals(False)
            return
        widget: QtWidgets.QLineEdit = self._input  # type: ignore[assignment]
        widget.blockSignals(True)
        widget.setText("" if value is None else str(value))
        widget.blockSignals(False)

    def value(self) -> Any:
        """Return the current editor value."""

        if self._multiline:
            widget: QtWidgets.QPlainTextEdit = self._input  # type: ignore[assignment]
            return widget.toPlainText()
        widget: QtWidgets.QLineEdit = self._input  # type: ignore[assignment]
        return widget.text()
