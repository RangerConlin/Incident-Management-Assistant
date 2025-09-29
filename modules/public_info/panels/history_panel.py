from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QDialog,
    QTextEdit,
    QDialogButtonBox,
    QAbstractItemView,
)

from modules.public_info.models.repository import PublicInfoRepository


TYPE_DISPLAY = [
    ("All", None),
    ("PressRelease", "PressRelease"),
    ("Advisory", "Advisory"),
    ("SituationUpdate", "SituationUpdate"),
]
AUDIENCE_DISPLAY = [("All", None), ("Public", "Public"), ("Agency", "Agency"), ("Internal", "Internal")]


class HistoryPanel(QWidget):
    def __init__(self, incident_id: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.incident_id = str(incident_id)
        self.repo = PublicInfoRepository(self.incident_id)

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(6)

        # Filters row
        h = QHBoxLayout()
        self.type_combo = QComboBox()
        for label, val in TYPE_DISPLAY:
            self.type_combo.addItem(label, val)
        self.audience_combo = QComboBox()
        for label, val in AUDIENCE_DISPLAY:
            self.audience_combo.addItem(label, val)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search...")
        self.btn_export = QPushButton("Export")
        h.addWidget(QLabel("Type"))
        h.addWidget(self.type_combo)
        h.addWidget(QLabel("Audience"))
        h.addWidget(self.audience_combo)
        h.addWidget(self.search_edit)
        h.addWidget(self.btn_export)
        vbox.addLayout(h)

        # Table: Published | Title | Audience | Type | Published By
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Published", "Title", "Audience", "Type", "Published By"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.doubleClicked.connect(self._preview_current)
        vbox.addWidget(self.table)

        # Inline status
        self.toast_label = QLabel("")
        self.toast_label.setStyleSheet("color: #666;")
        vbox.addWidget(self.toast_label)

        self.type_combo.currentIndexChanged.connect(self.refresh)
        self.audience_combo.currentIndexChanged.connect(self.refresh)
        self.search_edit.textChanged.connect(self.refresh)

    def refresh(self) -> None:
        t = self.type_combo.currentData()
        a = self.audience_combo.currentData()
        q = self.search_edit.text().strip() or None
        try:
            rows = self.repo.list_history(t, a, q)  # type: ignore[arg-type]
        except TypeError:
            rows = self.repo.list_history()
            rows = self._apply_client_filters(rows, t, a, q)
        self._populate(rows)

    def _apply_client_filters(
        self, rows: List[Dict[str, Any]], t: Optional[str], a: Optional[str], q: Optional[str]
    ) -> List[Dict[str, Any]]:
        def ok(r: Dict[str, Any]) -> bool:
            if t and r.get("type") != t:
                return False
            if a and r.get("audience") != a:
                return False
            if q and q.lower() not in (r.get("title", "") + "\n" + r.get("body", "")).lower():
                return False
            return True

        return [r for r in rows if ok(r)]

    def _populate(self, rows: List[Dict[str, Any]]):
        self.table.setRowCount(0)
        for r in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(r.get("published_at", "")))
            self.table.setItem(row, 1, QTableWidgetItem(r.get("title", "")))
            self.table.setItem(row, 2, QTableWidgetItem(r.get("audience", "")))
            self.table.setItem(row, 3, QTableWidgetItem(r.get("type", "")))
            self.table.setItem(row, 4, QTableWidgetItem(str(r.get("approved_by", ""))))

    def _preview_current(self):
        row = self.table.currentRow()
        if row < 0:
            return
        title = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
        audience = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
        mtype = self.table.item(row, 3).text() if self.table.item(row, 3) else ""
        published = self.table.item(row, 0).text() if self.table.item(row, 0) else ""
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Preview — {title}")
        v = QVBoxLayout(dlg)
        meta = QLabel(f"Audience: {audience} • Type: {mtype} • Published: {published}")
        v.addWidget(meta)
        body = QTextEdit()
        body.setReadOnly(True)
        body.setHtml("<i>Full body available in editor</i>")
        v.addWidget(body)
        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(dlg.reject)
        btns.accepted.connect(dlg.accept)
        v.addWidget(btns)
        dlg.resize(600, 400)
        dlg.exec()
