from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets


class AssignStepDialog(QtWidgets.QDialog):
    """Minimal person search, used to manually assign an approval step that
    has nobody resolved — either a flexible step by design, or a role-based
    step whose whole chain of command came up vacant."""

    def __init__(self, step_label: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Assign — {step_label}")
        self._person_record: Optional[int] = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel(f"Who should sign off on '{step_label}'?"))

        self._search = QtWidgets.QLineEdit()
        self._search.setPlaceholderText("Search personnel…")
        layout.addWidget(self._search)

        self._results = QtWidgets.QListWidget()
        layout.addWidget(self._results, 1)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(200)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._run_search)
        self._search.textChanged.connect(lambda *_: self._timer.start())

    def _run_search(self) -> None:
        from utils.api_client import api_client

        query = self._search.text().strip()
        self._results.clear()
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
            item.setData(QtCore.Qt.UserRole, int(record))
            self._results.addItem(item)

    def accept(self) -> None:
        item = self._results.currentItem()
        if item is None:
            QtWidgets.QMessageBox.information(self, "Assign", "Select a person first.")
            return
        self._person_record = item.data(QtCore.Qt.UserRole)
        super().accept()

    def selected_person_record(self) -> Optional[int]:
        return self._person_record


__all__ = ["AssignStepDialog"]
