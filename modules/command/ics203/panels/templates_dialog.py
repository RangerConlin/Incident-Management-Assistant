from __future__ import annotations

"""Dialog presenting reusable ICS-203 structure templates."""

from typing import List

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QListWidget,
    QListWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from ..models import OrgUnit, Position, TEMPLATES, render_template

SeedItem = tuple[str, OrgUnit | Position]


class TemplatesDialog(QDialog):
    """Allow operators to stamp predefined structures into an incident."""

    def __init__(self, incident_id: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ICS-203 Templates")
        self._incident_id = incident_id
        self._selected_items: list[SeedItem] = []

        layout = QVBoxLayout(self)
        self.lst_templates = QListWidget(self)
        for name in sorted(TEMPLATES.keys()):
            self.lst_templates.addItem(name)
        self.lst_templates.currentItemChanged.connect(self._update_preview)
        layout.addWidget(self.lst_templates)

        self.preview = QTextEdit(self)
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Select a template to preview the units and positions that will be created.")
        layout.addWidget(self.preview, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok, parent=self)
        buttons.button(QDialogButtonBox.Ok).setText("Apply")
        buttons.accepted.connect(self._handle_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if self.lst_templates.count():
            self.lst_templates.setCurrentRow(0)

    # ------------------------------------------------------------------
    def _update_preview(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None = None) -> None:
        if current is None:
            self.preview.clear()
            return
        name = current.text()
        items = render_template(name, self._incident_id)
        lines: list[str] = []
        for kind, obj in items:
            if isinstance(obj, OrgUnit):
                prefix = "Unit"
                details = f"{obj.unit_type} — {obj.name}"
            else:
                prefix = "Position"
                details = getattr(obj, "title", "")
            lines.append(f"{prefix}: {details}")
        self.preview.setPlainText("\n".join(lines) if lines else "Template is empty.")

    def _handle_accept(self) -> None:
        item = self.lst_templates.currentItem()
        if not item:
            self.reject()
            return
        name = item.text()
        self._selected_items = render_template(name, self._incident_id)
        self.accept()

    def selected_items(self) -> List[SeedItem]:
        return list(self._selected_items)
