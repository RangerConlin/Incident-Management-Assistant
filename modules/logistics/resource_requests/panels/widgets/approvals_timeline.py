"""Simple approvals timeline widget."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class ApprovalsTimeline(QtWidgets.QListWidget):
    """Read-only list representing the approval timeline."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.setFocusPolicy(QtCore.Qt.NoFocus)

    def set_approvals(self, approvals: list[dict[str, object]]) -> None:
        self.clear()
        for entry in approvals:
            text = f"{entry.get('ts_utc', '')} — {entry.get('action', '')}"
            actor = entry.get("actor_id")
            if actor:
                text += f" ({actor})"
            note = entry.get("note")
            if note:
                text += f"\n    {note}"
            self.addItem(text)
