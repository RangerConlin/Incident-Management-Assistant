"""Read-only dialog listing one item's full response history."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from utils.timefmt import format_display_datetime

from .. import api


class ResponseHistoryDialog(QDialog):
    def __init__(
        self, incident_id: str, checklist_id: str, item_id: str, item_label: str, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Response History — {item_label}")
        self.resize(480, 360)

        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        try:
            payload = api.get_item_history(incident_id, checklist_id, item_id)
            history: list[dict[str, Any]] = payload.get("history") or []
        except Exception as exc:  # noqa: BLE001
            self.list_widget.addItem(QListWidgetItem(f"Unable to load history: {exc}"))
            return

        if not history:
            self.list_widget.addItem(QListWidgetItem("No responses recorded yet."))
            return

        for entry in reversed(history):
            self.list_widget.addItem(QListWidgetItem(self._describe(entry)))

    def _describe(self, entry: dict[str, Any]) -> str:
        actor = api.resolve_person_display(entry.get("recorded_by"))
        when = format_display_datetime(entry.get("recorded_at"), include_seconds=False)
        if entry.get("na"):
            value_text = "N/A"
        else:
            value_text = str(entry.get("value"))
        notes = entry.get("notes") or ""
        line = f"{value_text} — {actor} at {when}"
        if notes:
            line += f"\nNotes: {notes}"
        return line


__all__ = ["ResponseHistoryDialog"]
