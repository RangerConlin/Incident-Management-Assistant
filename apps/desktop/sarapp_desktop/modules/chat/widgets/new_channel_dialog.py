"""Dialog for creating a new group chat channel, with an optional
(informational-only) participant list.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from utils.api_client import api_client


class NewChannelDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Channel")

        self._name_edit = QLineEdit(self)
        self._name_edit.setPlaceholderText("Channel name")

        self._participant_search = QLineEdit(self)
        self._participant_search.setPlaceholderText("Search personnel to add (optional)...")

        self._participant_list = QListWidget(self)
        self._participant_list.setSelectionMode(QAbstractItemView.MultiSelection)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Name"))
        layout.addWidget(self._name_edit)
        layout.addWidget(QLabel("Participants (optional)"))
        layout.addWidget(self._participant_search)
        layout.addWidget(self._participant_list)
        layout.addWidget(self._buttons)

        self._search_timer = QTimer(self)
        self._search_timer.setInterval(150)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._refresh_results)
        self._participant_search.textChanged.connect(lambda _: self._search_timer.start())

    def _refresh_results(self) -> None:
        query = self._participant_search.text().strip()
        try:
            results = api_client.get("/api/master/personnel", params={"search": query, "limit": 25}) or []
        except Exception:
            results = []
        self._participant_list.clear()
        for result in results:
            person_id = str(result.get("id") or "")
            name = str(result.get("name") or "")
            if not person_id or not name:
                continue
            item = QListWidgetItem(name)
            item.setData(1000, person_id)
            self._participant_list.addItem(item)

    @property
    def channel_name(self) -> str:
        return self._name_edit.text().strip()

    @property
    def participant_ids(self) -> list[str]:
        return [item.data(1000) for item in self._participant_list.selectedItems()]


__all__ = ["NewChannelDialog"]
