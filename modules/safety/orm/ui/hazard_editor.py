"""Dialog for adding/editing a canonical incident hazard."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from modules.admin.hazard_types.data.hazard_type_repository import (
    HAZARD_CATEGORIES,
    HAZARD_SOURCES,
    ApiHazardTypeRepository,
)

from .widgets.checkable_list import CheckableList
from .widgets.link_picker import LinkPickerDialog
from .widgets.spe_widget import SpeWidget


class HazardEditorDialog(QDialog):
    """Modal dialog used to add or edit a single canonical hazard."""

    @staticmethod
    def _normalize_default_op_period_ids(default_op_period: object) -> set[int]:
        if isinstance(default_op_period, dict):
            candidate = default_op_period.get("number") or default_op_period.get("id")
        else:
            candidate = default_op_period
        try:
            value = int(candidate)
        except (TypeError, ValueError):
            value = 1
        return {value}

    def __init__(
        self,
        incident_id: str,
        parent=None,
        *,
        hazard: Optional[dict] = None,
        default_op_period: object = 1,
    ):
        super().__init__(parent)
        self._incident_id = incident_id
        self.setWindowTitle("Add Hazard" if hazard is None else "Edit Hazard")
        self.setModal(True)
        self.resize(560, 720)
        self._result: Optional[dict[str, Any]] = None
        self._links: dict[str, list[int]] = {
            "work_assignment_ids": [],
            "team_ids": [],
            "task_ids": [],
        }
        self._hazard_types = ApiHazardTypeRepository().list_hazard_types()

        outer = QVBoxLayout(self)
        self._error_label = QLabel()
        self._error_label.setStyleSheet("color: #c62828; font-weight: 600;")
        self._error_label.hide()
        outer.addWidget(self._error_label)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll, 1)

        form_container = QWidget()
        scroll.setWidget(form_container)
        form = QFormLayout(form_container)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("e.g., Night movement in steep terrain")
        form.addRow("Title", self.title_edit)

        self.description_edit = QPlainTextEdit()
        self.description_edit.setMinimumHeight(56)
        form.addRow("Description", self.description_edit)

        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.addItems(list(HAZARD_CATEGORIES))
        form.addRow("Category", self.category_combo)

        self.hazard_type_combo = QComboBox()
        self.hazard_type_combo.addItem("(None)", None)
        for hazard_type in self._hazard_types:
            self.hazard_type_combo.addItem(
                hazard_type.get("name", ""), hazard_type
            )
        self.hazard_type_combo.currentIndexChanged.connect(self._on_hazard_type_changed)
        form.addRow("Hazard Type", self.hazard_type_combo)

        self.source_combo = QComboBox()
        self.source_combo.setEditable(True)
        self.source_combo.addItems(list(HAZARD_SOURCES))
        form.addRow("Source", self.source_combo)

        self.op_periods_list = CheckableList(
            [{"id": i} for i in range(1, 21)],
            "id",
            lambda d: str(d["id"]),
            self._normalize_default_op_period_ids(default_op_period),
            show_filter=False,
        )
        self.op_periods_list.setMaximumHeight(90)
        form.addRow("Operational Period(s)", self.op_periods_list)

        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("e.g., Division A / North Ridge")
        form.addRow("Location", self.location_edit)

        link_row = QHBoxLayout()
        self.link_summary_label = QLabel("No links")
        self.link_button = QPushButton("Link…")
        self.link_button.clicked.connect(self._open_link_picker)
        link_row.addWidget(self.link_summary_label, 1)
        link_row.addWidget(self.link_button)
        form.addRow("Linked Items", link_row)

        self.control_measure_edit = QPlainTextEdit()
        self.control_measure_edit.setMinimumHeight(56)
        form.addRow("Control Measure", self.control_measure_edit)

        self.mitigation_edit = QPlainTextEdit()
        self.mitigation_edit.setMinimumHeight(56)
        form.addRow("Mitigation", self.mitigation_edit)

        self.ppe_edit = QLineEdit()
        form.addRow("PPE", self.ppe_edit)

        self.safety_message_edit = QPlainTextEdit()
        self.safety_message_edit.setMinimumHeight(56)
        form.addRow("Safety Message", self.safety_message_edit)

        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setMinimumHeight(48)
        form.addRow("Notes", self.notes_edit)

        self.spe_initial = SpeWidget(default_enabled=True)
        form.addRow(QLabel("<b>Initial SPE Assessment</b>"))
        form.addRow(self.spe_initial)

        self.spe_residual = SpeWidget(default_enabled=False)
        form.addRow(QLabel("<b>Residual SPE Assessment</b>"))
        form.addRow(self.spe_residual)

        button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, Qt.Horizontal, self
        )
        button_box.accepted.connect(self._attempt_save)
        button_box.rejected.connect(self.reject)
        outer.addWidget(button_box)

        if hazard:
            self._populate(hazard)

    def _on_hazard_type_changed(self, index: int) -> None:
        hazard_type = self.hazard_type_combo.itemData(index)
        if not hazard_type:
            return
        if not self.control_measure_edit.toPlainText().strip() and hazard_type.get("default_control_measure"):
            self.control_measure_edit.setPlainText(hazard_type["default_control_measure"])
        if not self.ppe_edit.text().strip() and hazard_type.get("default_ppe"):
            self.ppe_edit.setText(hazard_type["default_ppe"])
        if not self.safety_message_edit.toPlainText().strip() and hazard_type.get("default_safety_message"):
            self.safety_message_edit.setPlainText(hazard_type["default_safety_message"])

    def _open_link_picker(self) -> None:
        dialog = LinkPickerDialog(
            self._incident_id,
            work_assignment_ids=self._links["work_assignment_ids"],
            team_ids=self._links["team_ids"],
            task_ids=self._links["task_ids"],
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            self._links = dialog.selected_links()
            self._update_link_summary()

    def _update_link_summary(self) -> None:
        total = sum(len(v) for v in self._links.values())
        if not total:
            self.link_summary_label.setText("No links")
        else:
            self.link_summary_label.setText(
                f"{len(self._links['work_assignment_ids'])} assignment(s), "
                f"{len(self._links['team_ids'])} team(s), "
                f"{len(self._links['task_ids'])} task(s)"
            )

    def _populate(self, hazard: dict) -> None:
        self.title_edit.setText(hazard.get("title", ""))
        self.description_edit.setPlainText(hazard.get("description") or "")
        self.category_combo.setCurrentText(hazard.get("category") or "")
        hazard_type_id = hazard.get("hazard_type_id")
        if hazard_type_id:
            for index in range(self.hazard_type_combo.count()):
                item = self.hazard_type_combo.itemData(index)
                if item and str(item.get("id")) == str(hazard_type_id):
                    self.hazard_type_combo.setCurrentIndex(index)
                    break
        self.source_combo.setCurrentText(hazard.get("source") or "")
        op_period_ids = set(hazard.get("op_period_ids") or [])
        if op_period_ids:
            for row in range(self.op_periods_list.list_widget.count()):
                item = self.op_periods_list.list_widget.item(row)
                item.setCheckState(
                    Qt.Checked if int(item.data(Qt.UserRole)) in op_period_ids else Qt.Unchecked
                )
        self.location_edit.setText(hazard.get("location_text") or "")
        links = hazard.get("links") or {}
        self._links = {
            "work_assignment_ids": list(links.get("work_assignment_ids") or []),
            "team_ids": list(links.get("team_ids") or []),
            "task_ids": list(links.get("task_ids") or []),
        }
        self._update_link_summary()
        self.control_measure_edit.setPlainText(hazard.get("control_measure") or "")
        self.mitigation_edit.setPlainText(hazard.get("mitigation_text") or "")
        self.ppe_edit.setText(hazard.get("ppe_text") or "")
        self.safety_message_edit.setPlainText(hazard.get("safety_message") or "")
        self.notes_edit.setPlainText(hazard.get("notes") or "")
        self.spe_initial.set_value(hazard.get("spe_initial"))
        self.spe_residual.set_value(hazard.get("spe_residual"))

    def _attempt_save(self) -> None:
        title = self.title_edit.text().strip()
        op_period_ids = self.op_periods_list.selected_ids()
        errors = []
        if not title:
            errors.append("Title is required.")
        if not op_period_ids:
            errors.append("At least one operational period is required.")
        if errors:
            self._error_label.setText(" ".join(errors))
            self._error_label.show()
            QMessageBox.warning(self, "Validation", "\n".join(errors))
            return

        hazard_type = self.hazard_type_combo.currentData()
        self._result = {
            "title": title,
            "description": self.description_edit.toPlainText().strip() or None,
            "category": self.category_combo.currentText().strip() or None,
            "hazard_type_id": str(hazard_type["id"]) if hazard_type else None,
            "hazard_type_text": hazard_type.get("name") if hazard_type else None,
            "source": self.source_combo.currentText().strip() or None,
            "op_period_ids": op_period_ids,
            "location_text": self.location_edit.text().strip() or None,
            "links": self._links,
            "control_measure": self.control_measure_edit.toPlainText().strip() or None,
            "mitigation_text": self.mitigation_edit.toPlainText().strip() or None,
            "ppe_text": self.ppe_edit.text().strip() or None,
            "safety_message": self.safety_message_edit.toPlainText().strip() or None,
            "notes": self.notes_edit.toPlainText().strip() or None,
            "spe_initial": self.spe_initial.value(),
            "spe_residual": self.spe_residual.value(),
        }
        self.accept()

    def result_payload(self) -> Optional[dict[str, Any]]:
        return self._result
