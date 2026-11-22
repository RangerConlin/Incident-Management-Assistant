"""Compact "Checklists" section embedded in a Planned-Event record's own
detail dialog (Assignment or Schedule Activity).

Lists checklists currently linked to that one record and lets the user
link an existing checklist, create one from the catalog (or blank), open
one, or remove an association — nothing more. This is deliberately not
the full master/detail `ChecklistsTab` or the execution widget itself (per
the product spec's "avoid a large relationship-management panel" and
"do not duplicate checklist item controls inside the Assignment editor"
constraints); opening a checklist uses `checklist_window.open_checklist_window`.
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from modules.checklists import api as checklist_api
from modules.checklists.progress_utils import progress_text, summarize
from modules.checklists.widgets.checklist_window import open_checklist_window
from modules.checklists.widgets.new_checklist_dialog import NewChecklistDialog


class ChecklistLinksSection(QWidget):
    def __init__(
        self, incident_id: str, record_type: str, record_id: str, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.incident_id = incident_id
        self.record_type = record_type
        self.record_id = record_id
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        header.addWidget(QLabel("Checklists"))
        header.addStretch(1)
        link_btn = QPushButton("Link Existing…")
        link_btn.clicked.connect(self._on_link_existing)
        create_btn = QPushButton("New Checklist…")
        create_btn.clicked.connect(self._on_create_new)
        header.addWidget(link_btn)
        header.addWidget(create_btn)
        layout.addLayout(header)

        self.list_widget = QListWidget()
        self.list_widget.setMaximumHeight(110)
        layout.addWidget(self.list_widget)

    def refresh(self) -> None:
        self.list_widget.clear()
        try:
            checklists = checklist_api.list_checklists(
                self.incident_id, linked_record_type=self.record_type, linked_record_id=self.record_id
            )
        except Exception as exc:  # noqa: BLE001
            self.list_widget.addItem(QListWidgetItem(f"Unable to load checklists: {exc}"))
            return
        if not checklists:
            self.list_widget.addItem(QListWidgetItem("No checklists linked."))
            return
        for checklist in checklists:
            self._add_row(checklist)

    def _add_row(self, checklist: dict[str, Any]) -> None:
        summary = summarize(checklist.get("sections"))
        status = str(checklist.get("status") or "not_started").replace("_", " ").title()
        text = f"{checklist.get('name', '')} — {status} — {progress_text(checklist.get('sections'))} answered"
        if summary["failed_items"]:
            text += f" — {len(summary['failed_items'])} unresolved failure(s)"
        item = QListWidgetItem(text)
        self.list_widget.addItem(item)

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addStretch(1)
        open_btn = QPushButton("Open")
        open_btn.clicked.connect(lambda _checked=False, cid=checklist["id"]: self._open_checklist(cid))
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(lambda _checked=False, cid=checklist["id"]: self._on_remove(cid))
        row_layout.addWidget(open_btn)
        row_layout.addWidget(remove_btn)
        item.setSizeHint(row_widget.sizeHint())
        self.list_widget.setItemWidget(item, row_widget)

    def _open_checklist(self, checklist_id: str) -> None:
        open_checklist_window(self.incident_id, checklist_id, self)

    def _on_remove(self, checklist_id: str) -> None:
        confirm = QMessageBox.question(
            self,
            "Remove Checklist Association",
            "Remove this checklist's association with this record? The checklist itself, its "
            "responses, and its other associations are preserved.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            checklist_api.remove_link(
                self.incident_id, checklist_id, record_type=self.record_type, record_id=self.record_id
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Remove Checklist Association", str(exc))
            return
        self.refresh()

    def _on_link_existing(self) -> None:
        try:
            all_checklists = checklist_api.list_checklists(self.incident_id)
            already_linked = checklist_api.list_checklists(
                self.incident_id, linked_record_type=self.record_type, linked_record_id=self.record_id
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Link Existing Checklist", str(exc))
            return
        linked_ids = {c["id"] for c in already_linked}
        candidates = [c for c in all_checklists if c["id"] not in linked_ids]
        if not candidates:
            QMessageBox.information(self, "Link Existing Checklist", "No other checklists are available to link.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Link Existing Checklist")
        layout = QVBoxLayout(dialog)
        combo = QComboBox()
        for checklist in candidates:
            combo.addItem(checklist.get("name", ""), checklist["id"])
        layout.addWidget(combo)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        checklist_id = combo.currentData()
        try:
            checklist_api.add_link(
                self.incident_id, checklist_id, record_type=self.record_type, record_id=self.record_id
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Link Existing Checklist", str(exc))
            return
        self.refresh()

    def _on_create_new(self) -> None:
        dialog = NewChecklistDialog(self.incident_id, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        payload = dialog.result_payload()
        try:
            if "template_id" in payload:
                created = checklist_api.create_checklist_from_template(
                    self.incident_id,
                    template_id=payload["template_id"],
                    name=payload["name"] or None,
                    owner_person_record=payload["owner_person_record"],
                )
            else:
                created = checklist_api.create_blank_checklist(
                    self.incident_id,
                    name=payload["name"],
                    sections=payload["sections"],
                    owner_person_record=payload["owner_person_record"],
                )
            checklist_api.add_link(
                self.incident_id, created["id"], record_type=self.record_type, record_id=self.record_id
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "New Checklist", str(exc))
            return
        self.refresh()


__all__ = ["ChecklistLinksSection"]
