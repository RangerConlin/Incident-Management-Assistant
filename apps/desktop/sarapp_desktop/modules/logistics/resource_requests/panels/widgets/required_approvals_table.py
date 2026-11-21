"""Required Approvals table — one table, rows grouped by the ICS-213RR
responsibility tier that owns that approval block (Requesting Section /
Logistics Section / Finance-Admin Section), matching apps/web/src/modules/
logistics/RequestHistory.tsx. Each section's still-pending row carries its
own inline note field and action buttons instead of a separate floating
note/action toolbar.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from PySide6 import QtCore, QtWidgets

from utils.table_view_styles import apply_statusboard_table_behavior

from ...models.enums import ACTION_SECTION_MAP, ApprovalAction, ApprovalSection, SECTION_PENDING_ACTIONS

SECTION_LABELS: Dict[ApprovalSection, str] = {
    ApprovalSection.REQUESTING: "Requesting Section",
    ApprovalSection.LOGISTICS: "Logistics Section",
    ApprovalSection.FINANCE: "Finance/Admin Section",
}
SECTION_ROLE_LABELS: Dict[ApprovalSection, str] = {
    ApprovalSection.REQUESTING: "Section Chief",
    ApprovalSection.LOGISTICS: "Logistics Section Chief",
    ApprovalSection.FINANCE: "Cost Approval",
}
ACTION_LABELS: Dict[ApprovalAction, str] = {
    ApprovalAction.SUBMIT: "Submit",
    ApprovalAction.REVIEW: "Review",
    ApprovalAction.APPROVE: "Approve",
    ApprovalAction.DENY: "Deny",
    ApprovalAction.CANCEL: "Cancel",
    ApprovalAction.REOPEN: "Reopen",
    ApprovalAction.FINANCE_APPROVE: "Approve",
    ApprovalAction.FINANCE_DENY: "Deny",
}

_COLUMNS = ["Section", "Status", "Actor", "When", "Note", "Actions"]


class RequiredApprovalsTable(QtWidgets.QTableWidget):
    """Dense desktop table — not a card/list layout — grouped by section."""

    actionRequested = QtCore.Signal(ApprovalAction, ApprovalSection, str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(0, len(_COLUMNS), parent)
        self.setHorizontalHeaderLabels(_COLUMNS)
        self.verticalHeader().setVisible(False)
        apply_statusboard_table_behavior(self, stretch_last_section=False)
        self._note_edits: Dict[ApprovalSection, QtWidgets.QLineEdit] = {}

    def set_data(
        self,
        approvals: List[Dict[str, object]],
        available_actions: List[ApprovalAction],
        terminal: bool,
    ) -> None:
        grouped: Dict[ApprovalSection, List[Dict[str, object]]] = {s: [] for s in ApprovalSection}
        for approval in approvals:
            action_value = str(approval.get("action", ""))
            try:
                action = ApprovalAction(action_value)
            except ValueError:
                continue
            section_value = approval.get("section")
            try:
                section = ApprovalSection(str(section_value)) if section_value else None
            except ValueError:
                section = None
            if section is None:
                section = ACTION_SECTION_MAP.get(action, ApprovalSection.LOGISTICS)
            grouped[section].append(approval)

        self._note_edits = {}
        self.setRowCount(len(ApprovalSection))
        for row, section in enumerate(ApprovalSection):
            entries = grouped[section]
            latest = entries[-1] if entries else None
            pending_actions = [a for a in SECTION_PENDING_ACTIONS[section] if a in available_actions]
            show_pending = not terminal and bool(pending_actions)

            section_item = QtWidgets.QTableWidgetItem(SECTION_LABELS[section])
            section_item.setToolTip(SECTION_ROLE_LABELS[section])
            section_item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            self.setItem(row, 0, section_item)

            if latest:
                status_text = ACTION_LABELS.get(ApprovalAction(str(latest.get("action"))), str(latest.get("action")))
            elif section is ApprovalSection.FINANCE:
                status_text = "Not Required"
            else:
                status_text = "Pending" if show_pending else "—"
            self._set_plain(row, 1, status_text)
            self._set_plain(row, 2, str(latest.get("actor_id")) if latest else "—")
            self._set_plain(row, 3, str(latest.get("ts_utc")) if latest else "—")

            if show_pending:
                note_edit = QtWidgets.QLineEdit(self)
                note_edit.setPlaceholderText("Note (required to deny)")
                self.setCellWidget(row, 4, note_edit)
                self._note_edits[section] = note_edit
            else:
                note_text = str(latest.get("note")) if latest and latest.get("note") else (
                    "No cost impact flagged on this request." if section is ApprovalSection.FINANCE and not latest else "—"
                )
                self._set_plain(row, 4, note_text)

            if show_pending:
                actions_widget = QtWidgets.QWidget(self)
                actions_layout = QtWidgets.QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(2, 2, 2, 2)
                actions_layout.setSpacing(4)
                for action in pending_actions:
                    button = QtWidgets.QPushButton(ACTION_LABELS[action], actions_widget)
                    button.clicked.connect(self._make_handler(action, section))
                    actions_layout.addWidget(button)
                actions_layout.addStretch(1)
                self.setCellWidget(row, 5, actions_widget)
            else:
                self._set_plain(row, 5, "—")

        self.resizeColumnsToContents()
        header = self.horizontalHeader()
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)

    def _make_handler(self, action: ApprovalAction, section: ApprovalSection) -> Callable[[], None]:
        def handler() -> None:
            note_edit = self._note_edits.get(section)
            note = note_edit.text().strip() if note_edit else ""
            if action in (ApprovalAction.DENY, ApprovalAction.FINANCE_DENY) and not note:
                QtWidgets.QMessageBox.warning(self, "Note Required", "Denial requires a note for audit trail compliance.")
                return
            self.actionRequested.emit(action, section, note)

        return handler

    def _set_plain(self, row: int, column: int, text: str) -> None:
        item = QtWidgets.QTableWidgetItem(text)
        item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
        self.setItem(row, column, item)
