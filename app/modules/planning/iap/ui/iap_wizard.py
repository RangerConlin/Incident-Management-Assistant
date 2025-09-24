"""Guided creation wizard for the IAP Builder."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from PySide6 import QtCore, QtWidgets

from ..models.iap_models import IAPPackage
from ..services.iap_service import DEFAULT_FORMS, IAPService


@dataclass
class WizardResult:
    """Container for the information produced by the wizard."""

    package: Optional[IAPPackage] = None


class IAPCreationWizard(QtWidgets.QDialog):
    """Multi-step dialog that walks users through creating a draft package."""

    def __init__(
        self,
        service: Optional[IAPService] = None,
        incident_id: str = "demo-incident",
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.service = service or IAPService()
        self.incident_id = incident_id
        self.result_container = WizardResult()

        self.setWindowTitle("New IAP Wizard")
        self.resize(720, 480)

        self._stack = QtWidgets.QStackedWidget()
        self._build_step_one()
        self._build_step_two()
        self._build_step_three()
        self._build_step_four()

        button_box = QtWidgets.QHBoxLayout()
        self.back_button = QtWidgets.QPushButton("< Back")
        self.next_button = QtWidgets.QPushButton("Next >")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        button_box.addWidget(self.back_button)
        button_box.addStretch()
        button_box.addWidget(self.next_button)
        button_box.addWidget(self.cancel_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._stack)
        layout.addLayout(button_box)

        self.back_button.clicked.connect(self._on_back)
        self.next_button.clicked.connect(self._on_next)
        self.cancel_button.clicked.connect(self.reject)

        self._update_buttons()

    # ------------------------------------------------------------------ steps
    def _build_step_one(self) -> None:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(page)
        self.op_number_spin = QtWidgets.QSpinBox()
        self.op_number_spin.setMinimum(1)
        self.op_number_spin.setValue(1)
        self.op_start_edit = QtWidgets.QDateTimeEdit()
        now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        self.op_start_edit.setDateTime(now)
        self.op_end_edit = QtWidgets.QDateTimeEdit()
        self.op_end_edit.setDateTime(now + timedelta(hours=12))
        self.profile_combo = QtWidgets.QComboBox()
        self.profile_combo.addItems(["State SAR", "With Aviation", "Custom"])
        layout.addRow("Operational Period #", self.op_number_spin)
        layout.addRow("Start", self.op_start_edit)
        layout.addRow("End", self.op_end_edit)
        layout.addRow("Profile", self.profile_combo)
        self._stack.addWidget(page)

    def _build_step_two(self) -> None:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        preset_layout = QtWidgets.QHBoxLayout()
        preset_layout.addWidget(QtWidgets.QLabel("Preset:"))
        self.preset_combo = QtWidgets.QComboBox()
        self.preset_combo.addItem("Standard Ground IAP", self._standard_ground_forms())
        self.preset_combo.addItem("With Aviation", self._ground_air_forms())
        self.preset_combo.addItem("Custom", [])
        preset_layout.addWidget(self.preset_combo)
        preset_layout.addStretch()
        layout.addLayout(preset_layout)

        self.form_list = QtWidgets.QListWidget()
        self.form_list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        layout.addWidget(self.form_list, 1)

        self.save_preset_button = QtWidgets.QPushButton("Save as Profile Preset")
        self.save_preset_button.clicked.connect(self._show_placeholder_message)
        layout.addWidget(self.save_preset_button)

        self._stack.addWidget(page)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        self._apply_forms(self._standard_ground_forms())

    def _build_step_three(self) -> None:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.addWidget(QtWidgets.QLabel("Autofill Sources"))
        self.summary_text = QtWidgets.QTextEdit()
        self.summary_text.setReadOnly(True)
        layout.addWidget(self.summary_text, 1)
        self._stack.addWidget(page)

    def _build_step_four(self) -> None:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        label = QtWidgets.QLabel("Draft created. Open the dashboard to continue editing.")
        label.setWordWrap(True)
        layout.addStretch()
        layout.addWidget(label, alignment=QtCore.Qt.AlignCenter)
        layout.addStretch()
        self.open_dashboard_button = QtWidgets.QPushButton("Open Dashboard")
        self.open_dashboard_button.clicked.connect(self.accept)
        layout.addWidget(self.open_dashboard_button, alignment=QtCore.Qt.AlignCenter)
        self._stack.addWidget(page)

    # ------------------------------------------------------------------ utilities
    def _update_buttons(self) -> None:
        index = self._stack.currentIndex()
        self.back_button.setEnabled(index > 0)
        if index == self._stack.count() - 1:
            self.next_button.setEnabled(False)
        elif index == self._stack.count() - 2:
            self.next_button.setText("Generate Draft")
            self.next_button.setEnabled(True)
        else:
            self.next_button.setText("Next >")
            self.next_button.setEnabled(True)

    def _standard_ground_forms(self) -> List[str]:
        return [
            "COVER",
            "ICS-202",
            "ICS-203",
            "ICS-204",
            "ICS-205",
            "ICS-206",
            "DIST",
        ]

    def _ground_air_forms(self) -> List[str]:
        forms = self._standard_ground_forms()
        forms.extend(["ICS-220"])
        return forms

    def _apply_forms(self, form_ids: List[str]) -> None:
        self.form_list.clear()
        for form_id, title in DEFAULT_FORMS.items():
            item = QtWidgets.QListWidgetItem(f"{title} ({form_id})")
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked if form_id in form_ids else QtCore.Qt.Unchecked)
            item.setData(QtCore.Qt.UserRole, form_id)
            self.form_list.addItem(item)

    def _selected_forms(self) -> List[str]:
        forms: List[str] = []
        for index in range(self.form_list.count()):
            item = self.form_list.item(index)
            if item.checkState() == QtCore.Qt.Checked:
                forms.append(item.data(QtCore.Qt.UserRole))
        return forms

    # ------------------------------------------------------------------ events
    def _on_back(self) -> None:
        index = self._stack.currentIndex()
        if index > 0:
            self._stack.setCurrentIndex(index - 1)
        self._update_buttons()

    def _on_next(self) -> None:
        index = self._stack.currentIndex()
        if index == self._stack.count() - 2:
            self._generate_draft()
            self._stack.setCurrentIndex(index + 1)
        else:
            if index == 1:
                self._populate_summary()
            self._stack.setCurrentIndex(index + 1)
        self._update_buttons()

    def _on_preset_changed(self, index: int) -> None:
        form_ids = self.preset_combo.itemData(index)
        if form_ids is None:
            form_ids = []
        self._apply_forms(list(form_ids))

    def _populate_summary(self) -> None:
        forms = self._selected_forms()
        summary_lines = ["Autofill sources are currently stubs:"]
        summary_lines.append(" - Incident Profile → 202 header/dates")
        summary_lines.append(" - Org/Personnel/Teams → 203, 204")
        summary_lines.append(" - Comms (master.db) → 205")
        summary_lines.append(" - Logistics/Aircraft → 220")
        summary_lines.append("")
        summary_lines.append("Forms included:")
        for form_id in forms:
            title = DEFAULT_FORMS.get(form_id, form_id)
            summary_lines.append(f"  • {title}")
        self.summary_text.setPlainText("\n".join(summary_lines))

    def _generate_draft(self) -> None:
        forms = self._selected_forms()
        if not forms:
            QtWidgets.QMessageBox.warning(self, "No Forms", "Select at least one form to generate a draft.")
            return
        package = self.service.create_package(
            incident_id=self.incident_id,
            op_number=self.op_number_spin.value(),
            op_start=self.op_start_edit.dateTime().toPython(),
            op_end=self.op_end_edit.dateTime().toPython(),
            forms=forms,
        )
        self.result_container.package = package

    def _show_placeholder_message(self) -> None:
        QtWidgets.QMessageBox.information(self, "Presets", "Saving presets will be available in a later milestone.")
