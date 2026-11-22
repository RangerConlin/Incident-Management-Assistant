"""Master/detail container combining the list and execution widgets.

This is the piece `modules/plannedtoolkit/windows.py` places as its
"Checklists" tab, but it is itself generic (constructed from an
`incident_id` alone) — nothing here is Planned-Events-specific, so another
module could host the same container, or just the execution widget
directly, later.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QMessageBox, QSplitter, QVBoxLayout, QWidget

from .. import api
from .checklist_execution_widget import ChecklistExecutionWidget
from .checklist_list_widget import ChecklistListWidget
from .new_checklist_dialog import NewChecklistDialog


class ChecklistsTab(QWidget):
    def __init__(self, incident_id: object | None = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.incident_id: Optional[str] = None if incident_id is None else str(incident_id)
        self._build_ui()
        self._subscribe_incident_changes()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)

        self.list_widget = ChecklistListWidget(self.incident_id)
        self.execution_widget = ChecklistExecutionWidget()
        splitter.addWidget(self.list_widget)
        splitter.addWidget(self.execution_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 900])
        layout.addWidget(splitter)

        self.list_widget.checklistSelected.connect(self._on_checklist_selected)
        self.list_widget.newChecklistRequested.connect(self._on_new_checklist_requested)
        self.execution_widget.checklistChanged.connect(self._on_execution_checklist_changed)

    # -- incident switching ---------------------------------------------------

    def set_incident(self, incident_id: object | None) -> None:
        normalized = None if incident_id is None else str(incident_id)
        if normalized == self.incident_id:
            return
        self.incident_id = normalized
        # Clear the stale detail view before the list even starts reloading,
        # so nothing from the previous incident stays visible while the new
        # incident's checklists load.
        self.execution_widget.clear()
        self.list_widget.set_incident(self.incident_id)

    def _subscribe_incident_changes(self) -> None:
        try:
            from utils.app_signals import app_signals

            app_signals.incidentChanged.connect(self._on_incident_changed)
        except Exception:
            pass

    def _on_incident_changed(self, incident_number: object) -> None:
        self.set_incident(incident_number)

    # -- wiring -----------------------------------------------------------

    def _on_checklist_selected(self, checklist: dict) -> None:
        checklist_id = checklist.get("id")
        if checklist_id and self.incident_id:
            self.execution_widget.load_checklist(self.incident_id, checklist_id)

    def _on_new_checklist_requested(self) -> None:
        if not self.incident_id:
            QMessageBox.warning(self, "New Checklist", "Select an incident before creating a checklist.")
            return
        dialog = NewChecklistDialog(self.incident_id, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        payload = dialog.result_payload()
        try:
            if "template_id" in payload:
                created = api.create_checklist_from_template(
                    self.incident_id,
                    template_id=payload["template_id"],
                    name=payload["name"] or None,
                    owner_person_record=payload["owner_person_record"],
                )
            else:
                created = api.create_blank_checklist(
                    self.incident_id,
                    name=payload["name"],
                    sections=payload["sections"],
                    owner_person_record=payload["owner_person_record"],
                )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "New Checklist", f"Unable to create checklist.\n{exc}")
            return
        self.list_widget.refresh()
        self.list_widget.select_checklist_id(created["id"])
        self.execution_widget.load_checklist(self.incident_id, created["id"])

    def _on_execution_checklist_changed(self, checklist: dict) -> None:
        if checklist:
            self.list_widget.update_checklist_in_place(checklist)


__all__ = ["ChecklistsTab"]
