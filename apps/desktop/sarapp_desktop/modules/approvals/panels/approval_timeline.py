from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from modules.approvals.models import ApprovalInstance, ApprovalStatus, StepStatus
from utils.styles import approval_status_colors, approval_step_status_colors, subscribe_theme

_OVERALL_LABELS: dict[ApprovalStatus, str] = {
    "not_started": "Not Started",
    "pending": "Pending",
    "approved": "Approved",
    "rejected": "Rejected",
}


class ApprovalTimeline(QtWidgets.QWidget):
    """Per-document approval chain widget — shows steps, status, and sign button."""

    sign_requested = QtCore.Signal(str)  # emits step_id
    assign_requested = QtCore.Signal(str, str)  # emits step_id, step label

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._state: ApprovalInstance | None = None
        self._current_person_record: int | None = None
        self._current_assignment_type: str | None = None
        self._setup_ui()
        subscribe_theme(self, lambda *_: self._refresh())

    def _setup_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._status_label = QtWidgets.QLabel()
        font = self._status_label.font()
        font.setBold(True)
        self._status_label.setFont(font)
        layout.addWidget(self._status_label)

        self._steps_layout = QtWidgets.QVBoxLayout()
        self._steps_layout.setSpacing(2)
        layout.addLayout(self._steps_layout)

    def set_state(
        self,
        state: ApprovalInstance | None,
        person_record: int | None = None,
        assignment_type: str | None = None,
    ) -> None:
        self._state = state
        self._current_person_record = person_record
        self._current_assignment_type = assignment_type
        self._refresh()

    def _refresh(self) -> None:
        while self._steps_layout.count():
            item = self._steps_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._state is None:
            self._status_label.setText("")
            return

        overall = _OVERALL_LABELS.get(self._state.status, self._state.status)
        self._status_label.setText(f"Approval status: {overall}")
        overall_colors = approval_status_colors().get(self._state.status)
        if overall_colors:
            self._status_label.setStyleSheet(f"color: {overall_colors['bg'].color().name()};")

        step_colors = approval_step_status_colors()
        for step in self._state.steps:
            row = QtWidgets.QHBoxLayout()

            indicator = QtWidgets.QLabel("●")
            colors = step_colors.get(step.status)
            if colors:
                indicator.setStyleSheet(f"color: {colors['bg'].color().name()};")
            row.addWidget(indicator)

            desc = step.label
            if step.resolved_role and step.resolved_role != step.role:
                desc += f" (escalated to {step.resolved_role})"
            label = QtWidgets.QLabel(desc)
            row.addWidget(label, 1)

            needs_assignment = step.status == "active" and step.kind != "ack" and step.resolved_actor_id is None
            if needs_assignment:
                btn = QtWidgets.QPushButton("Assign…")
                btn.setFixedWidth(70)
                btn.setToolTip("Nobody is resolved for this step — pick who should sign it.")
                step_id, step_label = step.step_id, step.label
                btn.clicked.connect(
                    lambda _checked, sid=step_id, lbl=step_label: self.assign_requested.emit(sid, lbl)
                )
                row.addWidget(btn)

            # Best-effort UI hint only — the sign endpoint is the real authority.
            can_sign = step.status == "active" and self._current_person_record is not None
            if can_sign and step.kind != "ack":
                can_sign = step.resolved_actor_id == self._current_person_record

            if can_sign:
                btn = QtWidgets.QPushButton("Sign")
                btn.setFixedWidth(60)
                step_id = step.step_id
                btn.clicked.connect(lambda _checked, sid=step_id: self.sign_requested.emit(sid))
                row.addWidget(btn)

            container = QtWidgets.QWidget()
            container.setLayout(row)
            self._steps_layout.addWidget(container)
