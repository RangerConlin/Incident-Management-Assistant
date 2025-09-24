"""Packet viewer that allows reordering forms and managing attachments."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets

from ..models.iap_models import IAPPackage
from ..services.iap_service import IAPService


class IAPPacketViewer(QtWidgets.QWidget):
    """Minimal packet viewer showing the packet outline and watermark toggle."""

    def __init__(
        self,
        package: IAPPackage,
        service: Optional[IAPService] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.package = package
        self.service = service or IAPService()
        self.setWindowTitle(f"Packet Viewer – OP {package.op_number}")
        self.resize(720, 520)
        self._build_ui()
        self._populate_forms()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        toolbar = QtWidgets.QHBoxLayout()
        self.back_button = QtWidgets.QPushButton("Back")
        self.save_button = QtWidgets.QPushButton("Save")
        self.export_button = QtWidgets.QPushButton("Export Draft PDF")
        self.watermark_combo = QtWidgets.QComboBox()
        self.watermark_combo.addItems(["DRAFT", "FINAL"])
        toolbar.addWidget(self.back_button)
        toolbar.addStretch()
        toolbar.addWidget(self.save_button)
        toolbar.addWidget(self.export_button)
        toolbar.addWidget(QtWidgets.QLabel("Watermark:"))
        toolbar.addWidget(self.watermark_combo)
        layout.addLayout(toolbar)

        self.forms_list = QtWidgets.QListWidget()
        self.forms_list.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.forms_list.setDefaultDropAction(QtCore.Qt.MoveAction)
        layout.addWidget(self.forms_list, 1)

        footer = QtWidgets.QHBoxLayout()
        self.add_attachment_button = QtWidgets.QPushButton("Add Attachment")
        self.remove_attachment_button = QtWidgets.QPushButton("Remove")
        footer.addWidget(self.add_attachment_button)
        footer.addWidget(self.remove_attachment_button)
        footer.addStretch()
        layout.addLayout(footer)

        self.save_button.clicked.connect(self._on_save)
        self.export_button.clicked.connect(self._on_export)
        self.add_attachment_button.clicked.connect(self._show_placeholder)
        self.remove_attachment_button.clicked.connect(self._show_placeholder)

    def _populate_forms(self) -> None:
        self.forms_list.clear()
        for form in self.package.forms:
            item = QtWidgets.QListWidgetItem(f"{form.title} ({form.form_id})")
            item.setData(QtCore.Qt.UserRole, form.form_id)
            self.forms_list.addItem(item)

    # ------------------------------------------------------------------ actions
    def _on_save(self) -> None:
        order = [self.forms_list.item(i).data(QtCore.Qt.UserRole) for i in range(self.forms_list.count())]
        reordered_forms = sorted(self.package.forms, key=lambda form: order.index(form.form_id))
        self.package.forms = reordered_forms
        QtWidgets.QMessageBox.information(self, "Saved", "Packet order saved (stub).")

    def _on_export(self) -> None:
        draft = self.watermark_combo.currentText() == "DRAFT"
        path = self.service.export_pdf(self.package, draft=draft)
        QtWidgets.QMessageBox.information(self, "Export", f"Packet exported to {path}.")

    def _show_placeholder(self) -> None:
        QtWidgets.QMessageBox.information(self, "Attachments", "Attachment management will be added later.")
