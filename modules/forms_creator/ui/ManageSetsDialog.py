"""Dialog for editing and removing form sets."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.forms.form_set_registry import FormSetRegistry
from .dialogs.NewFormSetDialog import NewFormSetDialog


class ManageSetsDialog(QDialog):
    """List all form sets with Edit / Remove actions per row."""

    def __init__(self, registry: FormSetRegistry, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Manage Form Sets")
        self.setMinimumSize(620, 340)
        self._registry = registry

        layout = QVBoxLayout(self)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Set ID", "Display Name", "Version", "Actions"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._refresh()

    def _refresh(self) -> None:
        sets = self._registry.list_sets()
        self._table.setRowCount(len(sets))
        for row, meta in enumerate(sets):
            self._table.setItem(row, 0, QTableWidgetItem(meta.id))
            self._table.setItem(row, 1, QTableWidgetItem(meta.display_name))
            self._table.setItem(row, 2, QTableWidgetItem(meta.version or ""))

            actions = QWidget()
            hbox = QHBoxLayout(actions)
            hbox.setContentsMargins(2, 2, 2, 2)
            hbox.setSpacing(4)

            edit_btn = QPushButton("Edit…")
            edit_btn.setFixedHeight(24)
            edit_btn.clicked.connect(
                lambda checked=False, sid=meta.id: self._on_edit(sid)
            )
            hbox.addWidget(edit_btn)

            remove_btn = QPushButton("Remove…")
            remove_btn.setFixedHeight(24)
            remove_btn.setStyleSheet("color: #cc3333;")
            remove_btn.clicked.connect(
                lambda checked=False, sid=meta.id, sname=meta.display_name: self._on_remove(sid, sname)
            )
            hbox.addWidget(remove_btn)
            hbox.addStretch()

            self._table.setCellWidget(row, 3, actions)

        self._table.resizeRowsToContents()

    def _on_edit(self, set_id: str) -> None:
        meta = self._registry.get_set(set_id)
        if not meta:
            return
        sets = self._registry.list_sets()
        existing_ids = {s.id for s in sets}
        existing_with_names = [(s.id, s.display_name) for s in sets if s.id != set_id]
        existing = {
            "id": meta.id,
            "display_name": meta.display_name,
            "version": meta.version,
            "fallback": meta.fallback,
        }
        dlg = NewFormSetDialog(existing_ids, existing_with_names, existing=existing, parent=self)
        if dlg.exec() != NewFormSetDialog.DialogCode.Accepted:
            return
        data = dlg.result_data()
        if not data:
            return
        self._registry.update_set(
            set_id=data["id"],
            display_name=data["display_name"],
            version=data["version"],
            fallback=data["fallback"],
        )
        self._refresh()

    def _on_remove(self, set_id: str, display_name: str) -> None:
        meta = self._registry.get_set(set_id)
        if not meta:
            return

        # Count form directories inside this set
        form_dirs = [d for d in meta.path.iterdir() if d.is_dir()] if meta.path.exists() else []
        content_warning = ""
        if form_dirs:
            content_warning = (
                f"\n\n⚠ This set contains {len(form_dirs)} form version(s). "
                f"All files inside will be permanently deleted."
            )

        reply = QMessageBox.question(
            self, "Remove Form Set",
            f"Permanently delete form set '{display_name}' ({set_id})?{content_warning}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._registry.remove_set(set_id)
        self._refresh()
