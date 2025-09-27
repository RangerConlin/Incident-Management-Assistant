from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QWidget

from modules.common.models.lookup_models import TaskTypesRepository

from .base_editor import BaseTypeEditorDialog, ColumnSpec


class TaskTypesEditorDialog(BaseTypeEditorDialog):
    window_title = "Task Types"
    settings_group = "TypeEditors/TaskTypes"
    columns = [
        ColumnSpec("is_active", "Active"),
        ColumnSpec("name", "Name"),
        ColumnSpec("category", "Category"),
        ColumnSpec("default_priority", "Default Priority"),
        ColumnSpec("description", "Description"),
        ColumnSpec("updated_at", "Updated"),
    ]
    repository = TaskTypesRepository
    has_priority_field = True

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
