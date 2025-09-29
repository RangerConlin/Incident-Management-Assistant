from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QAbstractItemView,
)

from modules.public_info.models.repository import PublicInfoRepository


STATUS_DISPLAY = [
    ("All", None),
    ("Draft", "Draft"),
    ("InReview", "InReview"),
    ("Approved", "Approved"),
    ("Published", "Published"),
    ("Archived", "Archived"),
]

TYPE_DISPLAY = [
    ("All", None),
    ("PressRelease", "PressRelease"),
    ("Advisory", "Advisory"),
    ("SituationUpdate", "SituationUpdate"),
]

AUDIENCE_DISPLAY = [("All", None), ("Public", "Public"), ("Agency", "Agency"), ("Internal", "Internal")]


class QueuePanel(QWidget):
    messageActivated = Signal(int)

    def __init__(self, incident_id: str, current_user: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.incident_id = str(incident_id)
        self.current_user = current_user or {"id": None, "roles": []}
        self.repo = PublicInfoRepository(self.incident_id)

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(6)

        # Filters row
        h = QHBoxLayout()
        self.status_combo = QComboBox()
        for label, val in STATUS_DISPLAY:
            self.status_combo.addItem(label, val)
        self.type_combo = QComboBox()
        for label, val in TYPE_DISPLAY:
            self.type_combo.addItem(label, val)
        self.audience_combo = QComboBox()
        for label, val in AUDIENCE_DISPLAY:
            self.audience_combo.addItem(label, val)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search...")
        h.addWidget(QLabel("Status"))
        h.addWidget(self.status_combo)
        h.addWidget(QLabel("Type"))
        h.addWidget(self.type_combo)
        h.addWidget(QLabel("Audience"))
        h.addWidget(self.audience_combo)
        h.addWidget(self.search_edit)
        vbox.addLayout(h)

        # Table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Status", "Type", "Audience", "Title", "Updated", "Author"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(False)
        self.table.doubleClicked.connect(self._on_double)
        vbox.addWidget(self.table)

        # Inline status label
        self.toast_label = QLabel("")
        self.toast_label.setStyleSheet("color: #666;")
        vbox.addWidget(self.toast_label)

        # Connect filters
        self.status_combo.currentIndexChanged.connect(self.refresh)
        self.type_combo.currentIndexChanged.connect(self.refresh)
        self.audience_combo.currentIndexChanged.connect(self.refresh)
        self.search_edit.textChanged.connect(self.refresh)

        # Keyboard shortcuts
        QShortcut(QKeySequence("/"), self, activated=lambda: self.search_edit.setFocus())
        QShortcut(QKeySequence("Return"), self, activated=self._on_double)
        QShortcut(QKeySequence("Space"), self, activated=self._on_double)
        QShortcut(QKeySequence("E"), self, activated=self._on_double)
        QShortcut(QKeySequence("A"), self, activated=self.approve_selected)
        QShortcut(QKeySequence("U"), self, activated=self.publish_selected)
        QShortcut(QKeySequence("Del"), self, activated=self.archive_selected)

    def focus_first_filter(self) -> None:
        self.status_combo.setFocus()

    def _on_double(self):
        mid = self.selected_message_id()
        if mid is not None:
            self.messageActivated.emit(mid)

    def selected_message_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        mid = item.data(Qt.UserRole)
        try:
            return int(mid) if mid is not None else None
        except Exception:
            return None

    def _filters(self) -> Dict[str, Optional[str]]:
        return {
            "status": self.status_combo.currentData(),
            "type": self.type_combo.currentData(),
            "audience": self.audience_combo.currentData(),
            "q": self.search_edit.text().strip() or None,
        }

    def refresh(self) -> None:
        f = self._filters()
        try:
            rows = self.repo.list_messages(
                status=f["status"], type=f["type"], audience=f["audience"], q=f["q"]
            )
        except TypeError:
            rows = self.repo.list_messages(
                status=f.get("status"), type=f.get("type"), audience=f.get("audience"), q=f.get("q")
            )
        self._populate(rows)

    def _populate(self, rows: List[Dict[str, Any]]):
        self.table.setRowCount(0)
        for r in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            status_item = QTableWidgetItem(r.get("status", ""))
            status_item.setData(Qt.UserRole, r.get("id"))
            self.table.setItem(row, 0, status_item)
            self.table.setItem(row, 1, QTableWidgetItem(r.get("type", "")))
            self.table.setItem(row, 2, QTableWidgetItem(r.get("audience", "")))
            self.table.setItem(row, 3, QTableWidgetItem(r.get("title", "")))
            self.table.setItem(row, 4, QTableWidgetItem(r.get("updated_at", "")))
            author = str(r.get("created_by", ""))
            self.table.setItem(row, 5, QTableWidgetItem(author))

    # Optional quick actions from queue
    def _selected(self) -> Optional[Dict[str, Any]]:
        mid = self.selected_message_id()
        if mid is None:
            return None
        try:
            msg = self.repo.get_message(mid)
            return msg
        except Exception:
            return None

    def approve_selected(self) -> None:
        msg = self._selected()
        if not msg:
            return
        try:
            self.repo.approve_message(int(msg["id"]), self.current_user)
            self.toast_label.setText("Approved")
        except Exception as e:
            self.toast_label.setText(str(e))
        finally:
            self.refresh()

    def publish_selected(self) -> None:
        msg = self._selected()
        if not msg:
            return
        try:
            self.repo.publish_message(int(msg["id"]), self.current_user)
            self.toast_label.setText("Published")
        except Exception as e:
            self.toast_label.setText(str(e))
        finally:
            self.refresh()

    def archive_selected(self) -> None:
        msg = self._selected()
        if not msg:
            return
        try:
            self.repo.archive_message(int(msg["id"]), self.current_user.get("id"))
            self.toast_label.setText("Archived")
        except Exception as e:
            self.toast_label.setText(str(e))
        finally:
            self.refresh()
