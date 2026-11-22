"""Open a single checklist in its own small floating window.

Used wherever something needs to "open a checklist" without the full
master/detail `ChecklistsTab` — e.g. from a Planned Events Schedule or
Assignment dialog's compact Checklists section, or when a checklist's own
"Associated Records" list navigates back to a record that, in turn, wants
to show that checklist. Non-modal (``show()``, not ``exec()``), so the
dialog underneath (a Schedule/Assignment editor) stays open and the user
returns to it exactly where they left off, without this window needing to
do anything special to "preserve" that selection.
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget

from .checklist_execution_widget import ChecklistExecutionWidget


class ChecklistWindow(QDialog):
    def __init__(self, incident_id: str, checklist_id: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Checklist")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(900, 700)

        layout = QVBoxLayout(self)
        self.execution_widget = ChecklistExecutionWidget()
        layout.addWidget(self.execution_widget)
        self.execution_widget.checklistChanged.connect(self._on_checklist_changed)
        self.execution_widget.load_checklist(incident_id, checklist_id)

    def _on_checklist_changed(self, checklist: dict[str, Any]) -> None:
        name = checklist.get("name") or "Checklist"
        self.setWindowTitle(f"Checklist — {name}")


def open_checklist_window(incident_id: str, checklist_id: str, parent: Optional[QWidget] = None) -> ChecklistWindow:
    window = ChecklistWindow(incident_id, checklist_id, parent)
    window.show()
    return window


__all__ = ["ChecklistWindow", "open_checklist_window"]
