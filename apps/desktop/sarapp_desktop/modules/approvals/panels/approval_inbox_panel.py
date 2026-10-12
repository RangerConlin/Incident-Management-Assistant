from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class ApprovalInboxPanel(QtWidgets.QWidget):
    """Cross-module pending approvals view, filtered to the current user's roles."""

    item_activated = QtCore.Signal(str, str)  # document_type, document_id

    def __init__(
        self,
        incident_id: str,
        person_record: int,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._incident_id = incident_id
        self._person_record = person_record
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        header = QtWidgets.QLabel("Pending Approvals")
        font = header.font()
        font.setPointSize(font.pointSize() + 2)
        font.setBold(True)
        header.setFont(font)
        layout.addWidget(header)

        self._refresh_btn = QtWidgets.QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self.load)
        layout.addWidget(self._refresh_btn, alignment=QtCore.Qt.AlignLeft)

        self._list = QtWidgets.QTreeWidget()
        self._list.setHeaderLabels(["Document", "Step", "Role"])
        self._list.setRootIsDecorated(False)
        self._list.itemActivated.connect(self._on_item_activated)
        layout.addWidget(self._list)

        self._empty_label = QtWidgets.QLabel("No pending approvals.")
        self._empty_label.setAlignment(QtCore.Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: #888888;")
        layout.addWidget(self._empty_label)
        self._empty_label.hide()

    def load(self) -> None:
        from modules.approvals.service import ApprovalService
        service = ApprovalService(self._incident_id)
        try:
            items = service.pending_for_person(self._person_record)
        except Exception:
            items = []
        self._populate(items)

    def _populate(self, items: list[dict]) -> None:
        self._list.clear()
        if not items:
            self._list.hide()
            self._empty_label.show()
            return
        self._empty_label.hide()
        self._list.show()
        for item in items:
            doc_type = item.get("document_type", "")
            doc_id = item.get("document_id", "")
            step_label = item.get("label", item.get("step_id", ""))
            role = item.get("role", "")
            row = QtWidgets.QTreeWidgetItem([
                f"{doc_type.upper()} #{doc_id}",
                step_label,
                role,
            ])
            row.setData(0, QtCore.Qt.UserRole, (doc_type, doc_id))
            self._list.addTopLevelItem(row)
        self._list.resizeColumnToContents(0)
        self._list.resizeColumnToContents(1)

    def _on_item_activated(self, item: QtWidgets.QTreeWidgetItem, _col: int) -> None:
        data = item.data(0, QtCore.Qt.UserRole)
        if data:
            self.item_activated.emit(data[0], data[1])

    def pending_count(self) -> int:
        return self._list.topLevelItemCount()
