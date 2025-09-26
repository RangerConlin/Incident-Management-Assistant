from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QWidget

from modules.common.models.lookup_models import TeamTypesRepository

from .base_editor import BaseTypeEditorDialog, ColumnSpec


class TeamTypesEditorDialog(BaseTypeEditorDialog):
    window_title = "Team Types"
    settings_group = "TypeEditors/TeamTypes"
    columns = [
        ColumnSpec("is_active", "Active"),
        ColumnSpec("name", "Name"),
        ColumnSpec("category", "Category"),
        ColumnSpec("description", "Description"),
        ColumnSpec("updated_at", "Updated"),
    ]
    repository = TeamTypesRepository

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
