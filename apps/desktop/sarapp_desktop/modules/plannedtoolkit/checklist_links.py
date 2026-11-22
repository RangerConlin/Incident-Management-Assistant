"""Registers Planned Events record types into
`modules.checklists.record_links`, so a checklist's "Associated Records"
list can show and open a linked Schedule Activity, Assignment, or (for a
promoted Assignment) the resulting Operations task — without
`modules.checklists` importing this module, or anything about Planned
Events, directly.

Imported once, purely for this registration side effect, from
`modules/plannedtoolkit/__init__.py`.
"""

from __future__ import annotations

from typing import Optional

from modules.checklists import record_links


def _resolve_schedule_label(incident_id: str, record_id: str) -> str:
    from . import services

    item = next((i for i in services.list_schedule_items(incident_id) if i.record_id == record_id), None)
    return item.name if item else record_id


def _open_schedule(incident_id: str, record_id: str, parent: object) -> None:
    from PySide6.QtWidgets import QDialog, QMessageBox

    from . import services
    from .widgets.schedule_dialogs import ScheduleItemDialog

    item = next((i for i in services.list_schedule_items(incident_id) if i.record_id == record_id), None)
    if item is None:
        QMessageBox.information(parent, "Schedule Activity", "This schedule activity is no longer available.")
        return
    dialog = ScheduleItemDialog(item, incident_id=incident_id, parent=parent)
    if dialog.exec() != QDialog.DialogCode.Accepted or item.id is None:
        return
    services.update_schedule_item(item.id, dialog.values(), incident_id)


def _find_assignment(incident_id: str, record_id: str):
    from . import services

    return next((r for r in services.list_records("quick-assignments", incident_id) if r.record_id == record_id), None)


def _resolve_assignment_label(incident_id: str, record_id: str) -> str:
    record = _find_assignment(incident_id, record_id)
    return record.title if record else record_id


def _open_assignment(incident_id: str, record_id: str, parent: object) -> None:
    from PySide6.QtWidgets import QDialog, QMessageBox

    from . import services
    from .widgets.assignment_detail_dialog import AssignmentDetailDialog

    record = _find_assignment(incident_id, record_id)
    if record is None:
        QMessageBox.information(parent, "Assignment", "This assignment is no longer available.")
        return
    dialog = AssignmentDetailDialog(parent, incident_id=incident_id, record=record)
    if dialog.exec() != QDialog.Accepted:
        return
    payload = dialog.result_payload()
    if payload and record.id is not None:
        services.update_record("quick-assignments", int(record.id), payload, incident_id)


def _find_task(incident_id: str, record_id: str) -> Optional[dict]:
    from utils.api_client import api_client

    try:
        tasks = api_client.get(f"/api/incidents/{incident_id}/tasks") or []
    except Exception:
        return None
    return next((task for task in tasks if task.get("task_id") == record_id), None)


def _resolve_task_label(incident_id: str, record_id: str) -> str:
    task = _find_task(incident_id, record_id)
    return (task.get("title") or record_id) if task else record_id


def _open_task(incident_id: str, record_id: str, parent: object) -> None:
    from PySide6.QtWidgets import QMessageBox

    task = _find_task(incident_id, record_id)
    if task is None:
        QMessageBox.information(parent, "Operations Task", "This task is no longer available.")
        return
    # Reuse the exact same opener `QuickAssignmentsPanel._open_tasking` uses
    # for "Open Task {id}" — never a second Operations-task UI.
    from modules.operations.taskings.windows import open_task_detail_window

    open_task_detail_window(incident_id, task.get("int_id") or task.get("id"))


record_links.register(
    "planned_schedule_item",
    record_links.RecordLinkHandler(
        type_label="Schedule Activity", resolve_label=_resolve_schedule_label, open_record=_open_schedule
    ),
)
record_links.register(
    "planned_quick_assignment",
    record_links.RecordLinkHandler(
        type_label="Assignment", resolve_label=_resolve_assignment_label, open_record=_open_assignment
    ),
)
record_links.register(
    "operations_task",
    record_links.RecordLinkHandler(
        type_label="Operations Task", resolve_label=_resolve_task_label, open_record=_open_task
    ),
)
