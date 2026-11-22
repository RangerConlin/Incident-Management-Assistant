"""Thin wrapper around `utils.styles.checklist_status_colors()`.

Keeps the checklist widgets from needing to know the exact title-case
status label keys used for the color lookup (vs. the lowercase
`not_started`/`in_progress`/... values the backend uses) in more than one
place.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QBrush

from utils.styles import checklist_status_colors

_LABELS = {
    "not_started": "Not Started",
    "in_progress": "In Progress",
    "completed": "Completed",
    "archived": "Archived",
}


def checklist_status_brush(status: str) -> Optional[dict[str, QBrush]]:
    label = _LABELS.get(status, status)
    return checklist_status_colors().get(label)
