"""Qt Widgets based dashboard for the IAP Builder."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from PySide6 import QtCore, QtWidgets

from ..services.iap_service import IAPService
from .components.autofill_preview_panel import AutofillPreviewPanel

if TYPE_CHECKING:  # pragma: no cover - imported for type checkers only
    from ..models.iap_models import IAPPackage


class IAPBuilderWindow(QtWidgets.QWidget):
    """Dashboard style window that mirrors the specification wireframes."""

    formSelected = QtCore.Signal(object)

    def __init__(
        self,
        service: Optional[IAPService] = None,
        incident_id: str = "demo-incident",
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.service = service or IAPService()
        self.incident_id = incident_id
        self._current_package: Optional[IAPPackage] = None
        self.setWindowTitle("IAP Builder")
        self.resize(1024, 720)

        self._build_ui()
        self._load_initial_data()

    # ------------------------------------------------------------------ UI setup
    def _build_ui(self) -> None:
        main_layout = QtWidgets.QVBoxLayout(self)
        header_box = QtWidgets.QGroupBox("Incident Action Plan")
        header_layout = QtWidgets.QGridLayout(header_box)

        self.incident_label = QtWidgets.QLabel()
        self.op_selector = QtWidgets.QComboBox()
        self.op_selector.currentIndexChanged.connect(self._on_op_changed)
        self.op_start_edit = QtWidgets.QDateTimeEdit()
        self.op_start_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.op_end_edit = QtWidgets.QDateTimeEdit()
        self.op_end_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.status_label = QtWidgets.QLabel("Draft")

        header_layout.addWidget(QtWidgets.QLabel("Incident:"), 0, 0)
        header_layout.addWidget(self.incident_label, 0, 1)
        header_layout.addWidget(QtWidgets.QLabel("Operational Period:"), 0, 2)
        header_layout.addWidget(self.op_selector, 0, 3)
        header_layout.addWidget(QtWidgets.QLabel("Start:"), 1, 0)
        header_layout.addWidget(self.op_start_edit, 1, 1)
        header_layout.addWidget(QtWidgets.QLabel("End:"), 1, 2)
        header_layout.addWidget(self.op_end_edit, 1, 3)
        header_layout.addWidget(QtWidgets.QLabel("Status:"), 2, 0)
        header_layout.addWidget(self.status_label, 2, 1)

        self.new_draft_button = QtWidgets.QPushButton("New Draft")
        self.publish_button = QtWidgets.QPushButton("Publish")
        self.export_button = QtWidgets.QPushButton("Export PDF")
        self.duplicate_button = QtWidgets.QPushButton("Duplicate OP")

        button_bar = QtWidgets.QHBoxLayout()
        button_bar.addWidget(self.new_draft_button)
        button_bar.addWidget(self.publish_button)
        button_bar.addWidget(self.export_button)
        button_bar.addWidget(self.duplicate_button)
        button_bar.addStretch()

        header_layout.addLayout(button_bar, 3, 0, 1, 4)

        main_layout.addWidget(header_box)

        splitter = QtWidgets.QSplitter(self)
        splitter.setOrientation(QtCore.Qt.Horizontal)
        main_layout.addWidget(splitter, 1)

        # Left column – form list and actions
        left_panel = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        splitter.addWidget(left_panel)

        self.forms_view = QtWidgets.QTreeWidget()
        self.forms_view.setColumnCount(3)
        self.forms_view.setHeaderLabels(["Form", "Last Edited", "Status"])
        self.forms_view.setRootIsDecorated(False)
        self.forms_view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.forms_view.currentItemChanged.connect(self._on_form_selection_changed)

        left_layout.addWidget(self.forms_view, 1)

        controls = QtWidgets.QHBoxLayout()
        self.add_form_button = QtWidgets.QPushButton("Add Form")
        self.remove_form_button = QtWidgets.QPushButton("Remove")
        self.reorder_button = QtWidgets.QPushButton("Reorder")
        controls.addWidget(self.add_form_button)
        controls.addWidget(self.remove_form_button)
        controls.addWidget(self.reorder_button)
        left_layout.addLayout(controls)

        action_bar = QtWidgets.QHBoxLayout()
        self.open_form_button = QtWidgets.QPushButton("Open Form")
        self.packet_viewer_button = QtWidgets.QPushButton("Packet Viewer")
        self.attachments_button = QtWidgets.QPushButton("Attachments")
        action_bar.addWidget(self.open_form_button)
        action_bar.addWidget(self.packet_viewer_button)
        action_bar.addWidget(self.attachments_button)
        left_layout.addLayout(action_bar)

        hint = QtWidgets.QLabel("Hints: Double-click a form to open editor. Ctrl+P = preview.")
        hint.setObjectName("iap-dashboard-hints")
        left_layout.addWidget(hint)

        # Right column – autofill preview and change log
        right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        splitter.addWidget(right_panel)

        self.autofill_panel = AutofillPreviewPanel(parent=right_panel)
        self.change_log = QtWidgets.QTextEdit()
        self.change_log.setReadOnly(True)
        self.change_log.setPlaceholderText("Change log will appear here.")

        right_layout.addWidget(self.autofill_panel)
        right_layout.addWidget(self.change_log)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        # Wire button placeholders
        self.new_draft_button.clicked.connect(self._on_new_draft)
        self.publish_button.clicked.connect(self._on_publish)
        self.export_button.clicked.connect(self._on_export)
        self.duplicate_button.clicked.connect(self._on_duplicate)
        self.add_form_button.clicked.connect(self._not_implemented)
        self.remove_form_button.clicked.connect(self._not_implemented)
        self.reorder_button.clicked.connect(self._not_implemented)
        self.open_form_button.clicked.connect(self._on_open_form)
        self.packet_viewer_button.clicked.connect(self._not_implemented)
        self.attachments_button.clicked.connect(self._not_implemented)

    def _load_initial_data(self) -> None:
        package = self.service.ensure_demo_package(self.incident_id, op_number=1)
        self._current_package = package
        self.incident_label.setText("Pine Ridge Wildfire")
        self._refresh_op_selector()
        self._populate_header(package)
        self._populate_forms(package)

    # --------------------------------------------------------------------- helpers
    def _refresh_op_selector(self) -> None:
        self.op_selector.blockSignals(True)
        self.op_selector.clear()
        packages = self.service.list_packages(self.incident_id)
        for package in packages:
            self.op_selector.addItem(f"OP {package.op_number}", package.op_number)
        if self._current_package:
            index = self.op_selector.findData(self._current_package.op_number)
            if index >= 0:
                self.op_selector.setCurrentIndex(index)
        self.op_selector.blockSignals(False)

    def _populate_header(self, package: IAPPackage) -> None:
        self.op_start_edit.setDateTime(package.op_start)
        self.op_end_edit.setDateTime(package.op_end)
        self.status_label.setText(package.status.upper())

    def _populate_forms(self, package: IAPPackage) -> None:
        self.forms_view.clear()
        for form in package.forms:
            status = "Started" if form.is_started else "Not Started"
            item = QtWidgets.QTreeWidgetItem([form.title, form.last_updated.strftime("%H:%M"), status])
            item.setData(0, QtCore.Qt.UserRole, form.form_id)
            if form.status == "published":
                item.setForeground(0, QtWidgets.QBrush(QtCore.Qt.darkGreen))
            self.forms_view.addTopLevelItem(item)
        if self.forms_view.topLevelItemCount():
            self.forms_view.setCurrentItem(self.forms_view.topLevelItem(0))

    # ------------------------------------------------------------------- callbacks
    def _on_op_changed(self, index: int) -> None:
        op_number = self.op_selector.itemData(index)
        if op_number is None:
            return
        try:
            package = self.service.get_package(self.incident_id, op_number)
        except KeyError:
            return
        self._current_package = package
        self._populate_header(package)
        self._populate_forms(package)

    def _on_form_selection_changed(self, current: QtWidgets.QTreeWidgetItem, previous: QtWidgets.QTreeWidgetItem) -> None:  # noqa: ARG002 - part of Qt API
        if current is None or self._current_package is None:
            self.autofill_panel.set_messages(["Select a form to view autofill preview."])
            return
        form_id = current.data(0, QtCore.Qt.UserRole)
        form = self._current_package.get_form(form_id)
        if form is None:
            self.autofill_panel.set_messages(["Form not found in package."])
            return
        preview = self.service.autofill_engine.preview_for_form(form)
        self.autofill_panel.set_preview(preview)
        self.formSelected.emit(form)

    def _on_new_draft(self) -> None:
        QtWidgets.QMessageBox.information(self, "Draft", "Draft creation will be implemented in a later milestone.")

    def _on_publish(self) -> None:
        if not self._current_package:
            return
        pdf_path = self.service.publish(self._current_package)
        self._populate_header(self._current_package)
        QtWidgets.QMessageBox.information(self, "Publish", f"Package published to {pdf_path}.")

    def _on_export(self) -> None:
        if not self._current_package:
            return
        pdf_path = self.service.export_pdf(self._current_package, draft=True)
        QtWidgets.QMessageBox.information(self, "Export", f"Draft exported to {pdf_path}.")

    def _on_duplicate(self) -> None:
        QtWidgets.QMessageBox.information(self, "Duplicate", "Duplicating operational periods will be added later.")

    def _on_open_form(self) -> None:
        if not self._current_package:
            return
        current_item = self.forms_view.currentItem()
        if not current_item:
            return
        form_id = current_item.data(0, QtCore.Qt.UserRole)
        form = self._current_package.get_form(form_id)
        if not form:
            return
        QtWidgets.QMessageBox.information(self, "Open Form", f"Opening form {form.title} is not yet implemented.")

    def _not_implemented(self) -> None:
        QtWidgets.QMessageBox.information(self, "Coming Soon", "This action will be implemented in a future milestone.")
