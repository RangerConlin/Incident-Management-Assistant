from __future__ import annotations

from typing import Any, Optional

from PySide6 import QtCore, QtWidgets


class _StepRow(QtWidgets.QWidget):
    """One line: step label, who it would go to, and a way to change that."""

    def __init__(self, row: dict[str, Any], parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.step_id: str = row["step_id"]
        self._chosen_record: Optional[int] = row.get("resolved_actor_id")
        self._chosen_name: str = row.get("resolved_actor_name") or ""

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel(f"<b>{row['label']}</b>"))
        top.addStretch()
        layout.addLayout(top)

        line = QtWidgets.QHBoxLayout()
        self._status_label = QtWidgets.QLabel()
        line.addWidget(self._status_label, 1)
        self._change_btn = QtWidgets.QPushButton("Change…")
        self._change_btn.setFixedWidth(80)
        self._change_btn.clicked.connect(self._toggle_search)
        line.addWidget(self._change_btn)
        layout.addLayout(line)

        self._search = QtWidgets.QLineEdit()
        self._search.setPlaceholderText("Search personnel…")
        self._search.hide()
        layout.addWidget(self._search)

        self._results = QtWidgets.QListWidget()
        self._results.setMaximumHeight(120)
        self._results.hide()
        layout.addWidget(self._results)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(200)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._run_search)
        self._search.textChanged.connect(lambda *_: self._timer.start())
        self._results.itemClicked.connect(self._on_result_picked)

        self._refresh_status()

    def _refresh_status(self) -> None:
        if self._chosen_record is None:
            self._status_label.setText("Nobody resolved — a person must be picked")
            self._status_label.setStyleSheet("color: #D97706;")
        else:
            self._status_label.setText(f"Will go to: {self._chosen_name or self._chosen_record}")
            self._status_label.setStyleSheet("")

    def _toggle_search(self) -> None:
        visible = not self._search.isVisible()
        self._search.setVisible(visible)
        self._results.setVisible(visible)
        if visible:
            self._search.setFocus()

    def _run_search(self) -> None:
        from utils.api_client import api_client

        query = self._search.text().strip()
        self._results.clear()
        if not query:
            return
        try:
            people = api_client.get("/api/master/personnel", params={"search": query, "limit": 25}) or []
        except Exception:
            people = []
        for person in people:
            record = person.get("person_record")
            if record is None:
                continue
            name = person.get("name") or f"Person {record}"
            role = person.get("primary_role") or ""
            item = QtWidgets.QListWidgetItem(f"{name} — {role}" if role else name)
            item.setData(QtCore.Qt.UserRole, (int(record), name))
            self._results.addItem(item)

    def _on_result_picked(self, item: QtWidgets.QListWidgetItem) -> None:
        record, name = item.data(QtCore.Qt.UserRole)
        self._chosen_record = record
        self._chosen_name = name
        self._search.hide()
        self._results.hide()
        self._search.clear()
        self._refresh_status()

    def chosen_record(self) -> Optional[int]:
        return self._chosen_record


class SubmitApprovalDialog(QtWidgets.QDialog):
    """Shows who each about-to-activate approval step would go to, with the
    option to change it, before the submitter commits to start/sign."""

    def __init__(self, title: str, rows: list[dict[str, Any]], parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self._rows: list[_StepRow] = []

        layout = QtWidgets.QVBoxLayout(self)
        for row in rows:
            widget = _StepRow(row)
            self._rows.append(widget)
            layout.addWidget(widget)
            layout.addWidget(self._separator())

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _separator() -> QtWidgets.QFrame:
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        return line

    def accept(self) -> None:
        if any(row.chosen_record() is None for row in self._rows):
            QtWidgets.QMessageBox.information(
                self, "Submit", "Pick a person for every step that has nobody resolved."
            )
            return
        super().accept()

    def chosen_actors(self) -> dict[str, int]:
        return {row.step_id: row.chosen_record() for row in self._rows if row.chosen_record() is not None}


__all__ = ["SubmitApprovalDialog"]
