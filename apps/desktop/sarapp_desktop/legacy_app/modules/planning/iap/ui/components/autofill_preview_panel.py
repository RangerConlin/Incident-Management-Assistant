"""Widget that surfaces autofill previews next to the form editor or dashboard."""

from __future__ import annotations

from typing import Iterable

from PySide6 import QtWidgets

from ...models.autofill import AutofillResult


class AutofillPreviewPanel(QtWidgets.QGroupBox):
    """Tiny helper widget that shows autofill summary information."""

    def __init__(self, title: str = "Autofill Preview", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(title, parent)
        self._text = QtWidgets.QTextEdit(self)
        self._text.setReadOnly(True)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._text)

    def set_preview(self, preview: AutofillResult | None) -> None:
        """Render ``preview`` into the text edit."""

        if preview is None:
            self._text.setPlainText("No autofill information available.")
            return
        lines = [f"Form: {preview.form_id}"]
        if preview.populated_fields:
            lines.append("")
            lines.append("Populated Fields:")
            for field, value in preview.populated_fields.items():
                lines.append(f"  - {field}: {value}")
        if preview.sources:
            lines.append("")
            lines.append("Sources:")
            for field, source in preview.sources.items():
                lines.append(f"  - {field}: {source}")
        self._text.setPlainText("\n".join(lines))

    def set_messages(self, messages: Iterable[str]) -> None:
        """Render arbitrary summary text."""

        self._text.setPlainText("\n".join(messages))
