from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from modules.approvals.models import ApprovalInstance, ApprovalStatus, StepStatus

_STATUS_COLORS: dict[StepStatus, str] = {
    "waiting": "#888888",
    "active": "#E6A817",
    "completed": "#3D9970",
    "skipped": "#AAAAAA",
}

_OVERALL_LABELS: dict[ApprovalStatus, str] = {
    "not_started": "Not Started",
    "pending": "Pending",
    "approved": "Approved",
    "rejected": "Rejected",
}


class ApprovalTimeline(QtWidgets.QWidget):
    """Per-document approval chain widget — shows steps, status, and sign button."""

    sign_requested = QtCore.Signal(str)  # emits step_id

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._state: ApprovalInstance | None = None
        self._current_personnel_id: str | None = None
        self._current_assignment_type: str | None = None
        self._setup_ui()

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
        personnel_id: str | None = None,
        assignment_type: str | None = None,
    ) -> None:
        self._state = state
        self._current_personnel_id = personnel_id
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

        for step in self._state.steps:
            row = QtWidgets.QHBoxLayout()

            indicator = QtWidgets.QLabel("●")
            color = _STATUS_COLORS.get(step.status, "#888888")
            indicator.setStyleSheet(f"color: {color};")
            row.addWidget(indicator)

            desc = step.label
            if step.resolved_role and step.resolved_role != step.role:
                desc += f" (escalated to {step.resolved_role})"
            label = QtWidgets.QLabel(desc)
            row.addWidget(label, 1)

            can_sign = (
                step.status == "active"
                and self._current_personnel_id is not None
                and self._state is not None
            )
            if can_sign:
                from modules.approvals.service import ApprovalService
                # Inline check without hitting the server for UI responsiveness
                if step.kind == "ack":
                    can_sign = True
                elif step.resolved_actor_id:
                    can_sign = step.resolved_actor_id == self._current_personnel_id

            if can_sign:
                btn = QtWidgets.QPushButton("Sign")
                btn.setFixedWidth(60)
                step_id = step.step_id
                btn.clicked.connect(lambda _checked, sid=step_id: self.sign_requested.emit(sid))
                row.addWidget(btn)

            container = QtWidgets.QWidget()
            container.setLayout(row)
            self._steps_layout.addWidget(container)
