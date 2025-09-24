"""Qt Widgets based dashboard for the IAP Builder."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Optional, TYPE_CHECKING

from PySide6 import QtCore, QtWidgets

from ..services.iap_service import IAPService
from .components.autofill_preview_panel import AutofillPreviewPanel
from utils import incident_context
from utils.state import AppState

if TYPE_CHECKING:  # pragma: no cover - imported for type checkers only
    from ..models.iap_models import IAPPackage


_LOGGER = logging.getLogger(__name__)


class IAPBuilderWindow(QtWidgets.QWidget):
    """Dashboard style window that mirrors the specification wireframes."""

    formSelected = QtCore.Signal(object)

    def __init__(
        self,
        service: Optional[IAPService] = None,
        incident_id: Optional[str] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        resolved_incident = self._resolve_incident_id(incident_id)
        self.service = service or IAPService(incident_id=resolved_incident)
        self.incident_id = resolved_incident or ""
        self._packages: Dict[int, IAPPackage] = {}
        self._current_package: Optional[IAPPackage] = None
        self.setWindowTitle("IAP Builder")
        self.resize(1024, 720)

        self._build_ui()

        if not resolved_incident:
            self._show_missing_repository_state("Select or create an incident to open the IAP Builder.")
            return

        if not self.service.repository:
            self._show_missing_repository_state("Incident database unavailable for the selected incident.")
            return

        self._load_initial_data()

    # ------------------------------------------------------------------ UI setup
    def _resolve_incident_id(self, provided: Optional[str]) -> Optional[str]:
        if provided:
            return provided
        active = AppState.get_active_incident()
        if active:
            return str(active)
        try:
            return incident_context.get_active_incident_id()
        except Exception:  # pragma: no cover - defensive
            return None

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

    def _show_missing_repository_state(self, message: str) -> None:
        self.incident_label.setText(message)
        self.op_selector.clear()
        self.op_selector.addItem("No IAP packages", None)
        self.op_selector.setEnabled(False)
        for widget in (
            self.new_draft_button,
            self.publish_button,
            self.export_button,
            self.duplicate_button,
            self.add_form_button,
            self.remove_form_button,
            self.reorder_button,
            self.open_form_button,
            self.packet_viewer_button,
            self.attachments_button,
        ):
            widget.setEnabled(False)
        self.forms_view.clear()
        self.forms_view.setEnabled(False)
        self.autofill_panel.set_messages([message])
        self.change_log.clear()

    def _reload_packages(self) -> None:
        try:
            packages = self.service.list_packages(self.incident_id)
        except Exception:  # pragma: no cover - defensive logging
            _LOGGER.exception("Failed to load IAP packages for incident %s", self.incident_id)
            packages = []
        self._packages = {pkg.op_number: pkg for pkg in packages}

    def _load_initial_data(self) -> None:
        self.incident_label.setText(self.service.incident_display_name(self.incident_id))
        self._reload_packages()
        if not self._packages:
            self._set_current_package(None)
            self._refresh_op_selector()
            self.autofill_panel.set_messages(["No IAP packages found for this incident."])
            return
        first_op = sorted(self._packages)[0]
        self._set_current_package(self._packages[first_op])
        self._refresh_op_selector()

    # --------------------------------------------------------------------- helpers
    def _refresh_op_selector(self) -> None:
        self.op_selector.blockSignals(True)
        self.op_selector.clear()
        if not self._packages:
            self.op_selector.addItem("No IAP packages", None)
            self.op_selector.setEnabled(False)
        else:
            self.op_selector.setEnabled(True)
            for op_number in sorted(self._packages):
                self.op_selector.addItem(f"OP {op_number}", op_number)
            if self._current_package:
                index = self.op_selector.findData(self._current_package.op_number)
                if index >= 0:
                    self.op_selector.setCurrentIndex(index)
        self.op_selector.blockSignals(False)

    def _set_current_package(self, package: Optional[IAPPackage]) -> None:
        self._current_package = package
        if package is None:
            self._clear_package_view()
        else:
            self.forms_view.setEnabled(True)
            self._populate_header(package)
            self._populate_forms(package)

    def _clear_package_view(self) -> None:
        now = datetime.utcnow()
        self.op_start_edit.setDateTime(now)
        self.op_end_edit.setDateTime(now)
        self.status_label.setText("No Package")
        self.forms_view.clear()
        self.forms_view.setEnabled(False)
        self.autofill_panel.set_messages(["Select an operational period or create a new draft."])
        self.change_log.clear()

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
        else:
            self.autofill_panel.set_messages(["No forms have been added to this package yet."])

    # ------------------------------------------------------------------- callbacks
    def _on_op_changed(self, index: int) -> None:
        op_number = self.op_selector.itemData(index)
        if op_number is None:
            self._set_current_package(None)
            return
        package = self._packages.get(op_number)
        if package is None:
            try:
                package = self.service.get_package(self.incident_id, op_number)
            except Exception:  # pragma: no cover - defensive logging
                _LOGGER.exception("Unable to load package OP %s", op_number)
                self._set_current_package(None)
                return
            self._packages[op_number] = package
        self._set_current_package(package)

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
        try:
            pdf_path = self.service.publish(self._current_package)
        except Exception as exc:  # pragma: no cover - user facing guard
            QtWidgets.QMessageBox.warning(self, "Publish", f"Unable to publish package: {exc}")
            return
        self._reload_packages()
        op_number = self._current_package.op_number
        if op_number in self._packages:
            self._set_current_package(self._packages[op_number])
            self._refresh_op_selector()
        QtWidgets.QMessageBox.information(self, "Publish", f"Package published to {pdf_path}.")

    def _on_export(self) -> None:
        if not self._current_package:
            return
        try:
            pdf_path = self.service.export_pdf(self._current_package, draft=True)
        except Exception as exc:  # pragma: no cover - user facing guard
            QtWidgets.QMessageBox.warning(self, "Export", f"Unable to export draft: {exc}")
            return
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
