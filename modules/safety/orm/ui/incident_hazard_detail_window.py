"""Reusable detail window for creating and editing an incident hazard."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from modules.admin.hazard_types.data.hazard_type_repository import ApiHazardTypeRepository
from modules.admin.hazard_types.models.hazard_type_models import (
    EXPOSURE_OPTIONS,
    HAZARD_CATEGORIES,
    PROBABILITY_OPTIONS,
    SEVERITY_OPTIONS,
)
from modules.admin.hazard_types.windows.hazard_type_editor_window import StringListEditor
from modules.safety.orm.scoring import spe_band, spe_score
from utils.api_client import api_client

from .widgets.checkable_list import CheckableList
from .widgets.link_picker import LinkPickerDialog


def _fetch_hazard_zones(incident_id: str) -> list[dict[str, Any]]:
    try:
        rows = api_client.get(f"/api/incidents/{incident_id}/gis/features/by-type/hazard_zone") or []
    except Exception:
        return []
    normalized = []
    for row in rows:
        item = dict(row)
        item["id"] = item.get("id") or item.get("int_id")
        if item["id"] is not None:
            normalized.append(item)
    return normalized


def _split_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _spe_to_dict(assessment: object) -> dict[str, Any] | None:
    if assessment is None:
        return None
    if isinstance(assessment, dict):
        return assessment
    return {
        "severity": getattr(assessment, "severity", 1),
        "probability": getattr(assessment, "probability", 1),
        "exposure": getattr(assessment, "exposure", 1),
    }


class SpeAssessmentEditor(QWidget):
    """Dropdown-based SPE editor with computed score, band, action, and definitions."""

    def __init__(self, title: str, *, assessed: bool = True, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.assessed_combo = QComboBox()
        self.assessed_combo.addItem("Assessed", True)
        self.assessed_combo.addItem("Not assessed", False)
        self.assessed_combo.setCurrentIndex(0 if assessed else 1)

        header = QHBoxLayout()
        label = QLabel(title)
        label.setStyleSheet("font-weight: 700;")
        header.addWidget(label)
        header.addStretch(1)
        header.addWidget(self.assessed_combo)
        layout.addLayout(header)

        selectors = QGridLayout()
        self.severity_combo = QComboBox()
        self.probability_combo = QComboBox()
        self.exposure_combo = QComboBox()
        self._load_option_items(self.severity_combo, SEVERITY_OPTIONS)
        self._load_option_items(self.probability_combo, PROBABILITY_OPTIONS)
        self._load_option_items(self.exposure_combo, EXPOSURE_OPTIONS)
        selectors.addWidget(QLabel("Severity"), 0, 0)
        selectors.addWidget(QLabel("Probability"), 0, 1)
        selectors.addWidget(QLabel("Exposure"), 0, 2)
        selectors.addWidget(self.severity_combo, 1, 0)
        selectors.addWidget(self.probability_combo, 1, 1)
        selectors.addWidget(self.exposure_combo, 1, 2)
        layout.addLayout(selectors)

        results = QHBoxLayout()
        score_frame, self.score_value = self._create_result_frame("Score")
        band_frame, self.band_value = self._create_result_frame("Band")
        action_frame, self.action_value = self._create_result_frame("Action")
        results.addWidget(score_frame)
        results.addWidget(band_frame)
        results.addWidget(action_frame)
        layout.addLayout(results)

        definitions = QGridLayout()
        definitions.addWidget(
            self._build_definition_box(
                "Severity",
                "Potential consequences measured in damage, injury, or incident impact.",
                SEVERITY_OPTIONS,
            ),
            0,
            0,
        )
        definitions.addWidget(
            self._build_definition_box(
                "Probability",
                "Likelihood that the potential consequences will occur.",
                PROBABILITY_OPTIONS,
            ),
            0,
            1,
        )
        definitions.addWidget(
            self._build_definition_box(
                "Exposure",
                "Amount of time, repetition, people, or equipment involved.",
                EXPOSURE_OPTIONS,
            ),
            0,
            2,
        )
        layout.addLayout(definitions)

        self.assessed_combo.currentIndexChanged.connect(self._on_changed)
        self.severity_combo.currentIndexChanged.connect(self._on_changed)
        self.probability_combo.currentIndexChanged.connect(self._on_changed)
        self.exposure_combo.currentIndexChanged.connect(self._on_changed)
        self._on_changed()

    def _load_option_items(self, combo: QComboBox, options: tuple[tuple[int, str], ...]) -> None:
        for value, label in options:
            combo.addItem(f"{value} - {label}", value)

    def _create_result_frame(self, title: str) -> tuple[QFrame, QLabel]:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(QLabel(title))
        value = QLabel("")
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(value)
        return frame, value

    def _build_definition_box(
        self,
        title: str,
        description: str,
        options: tuple[tuple[int, str], ...],
    ) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        title_label = QLabel(title)
        title_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(title_label)
        description_label = QLabel(description)
        description_label.setWordWrap(True)
        layout.addWidget(description_label)
        scale = QLabel("\n".join(f"{value} = {label}" for value, label in options))
        scale.setWordWrap(True)
        scale.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(scale)
        return frame

    def _current_combo_value(self, combo: QComboBox) -> int:
        data = combo.currentData()
        return int(data) if data is not None else 1

    def _set_combo_value(self, combo: QComboBox, value: int) -> None:
        for index in range(combo.count()):
            if int(combo.itemData(index)) == int(value):
                combo.setCurrentIndex(index)
                return
        combo.setCurrentIndex(0)

    def _is_assessed(self) -> bool:
        return bool(self.assessed_combo.currentData())

    def _on_changed(self) -> None:
        assessed = self._is_assessed()
        for combo in (self.severity_combo, self.probability_combo, self.exposure_combo):
            combo.setEnabled(assessed)
        if not assessed:
            self.score_value.setText("Not assessed")
            self.band_value.setText("Not assessed")
            self.action_value.setText("")
            return
        score = spe_score(
            self._current_combo_value(self.severity_combo),
            self._current_combo_value(self.probability_combo),
            self._current_combo_value(self.exposure_combo),
        )
        band, action = spe_band(score)
        self.score_value.setText(str(score))
        self.band_value.setText(band)
        self.action_value.setText(action)

    def set_value(self, assessment: object) -> None:
        data = _spe_to_dict(assessment)
        if not data:
            self.assessed_combo.setCurrentIndex(1)
            self._on_changed()
            return
        self.assessed_combo.setCurrentIndex(0)
        self._set_combo_value(self.severity_combo, int(data.get("severity") or 1))
        self._set_combo_value(self.probability_combo, int(data.get("probability") or 1))
        self._set_combo_value(self.exposure_combo, int(data.get("exposure") or 1))
        self._on_changed()

    def value(self) -> Optional[dict[str, int]]:
        if not self._is_assessed():
            return None
        return {
            "severity": self._current_combo_value(self.severity_combo),
            "probability": self._current_combo_value(self.probability_combo),
            "exposure": self._current_combo_value(self.exposure_combo),
        }


class IncidentHazardDetailWindow(QDialog):
    """Reusable window used to add or edit a single canonical incident hazard."""

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
        default_work_assignment_id: int | None = None,
    ):
        super().__init__(parent)
        self._incident_id = incident_id
        self._hazard = hazard or {}
        self._result: Optional[dict[str, Any]] = None
        self._links: dict[str, list[int]] = {
            "work_assignment_ids": [int(default_work_assignment_id)] if default_work_assignment_id else [],
            "team_ids": [],
            "task_ids": [],
        }
        self._hazard_types = ApiHazardTypeRepository().list_hazard_types()

        self.setWindowTitle("New Incident Hazard Detail" if hazard is None else "Incident Hazard Detail")
        self.setModal(True)
        self.resize(980, 760)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)
        root.addWidget(self._build_header())

        self._error_label = QLabel()
        self._error_label.setStyleSheet("color: #c62828; font-weight: 600;")
        self._error_label.hide()
        root.addWidget(self._error_label)

        tabs = QTabWidget()
        tabs.addTab(self._build_hazard_tab(), "Hazard Details")
        tabs.addTab(self._build_safety_content_tab(), "Safety Content")
        tabs.addTab(self._build_spe_tab(), "SPE Assessment")
        tabs.addTab(self._build_links_tab(default_op_period), "Links")
        tabs.addTab(self._build_notes_tab(), "Notes / Metadata")
        root.addWidget(tabs, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._attempt_save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        if hazard:
            self._populate(hazard)
        else:
            self._update_source_summary()

    def _build_header(self) -> QWidget:
        header = QGroupBox("Incident Hazard")
        layout = QGridLayout(header)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("e.g., Night movement in steep terrain")
        self.category_combo = QComboBox()
        self.category_combo.addItems(HAZARD_CATEGORIES)

        self.hazard_type_combo = QComboBox()
        self.hazard_type_combo.addItem("(Incident-only hazard)", None)
        for hazard_type in self._hazard_types:
            self.hazard_type_combo.addItem(hazard_type.get("name", ""), hazard_type)
        self.hazard_type_combo.currentIndexChanged.connect(self._update_source_summary)

        self.copy_library_button = QPushButton("Copy From Library")
        self.copy_library_button.clicked.connect(self._copy_selected_library_hazard)
        self.source_summary_label = QLabel()
        self.source_summary_label.setWordWrap(True)
        self.source_summary_label.setStyleSheet("color: #5f6b7a;")

        layout.addWidget(QLabel("Hazard name *"), 0, 0)
        layout.addWidget(self.title_edit, 0, 1, 1, 3)
        layout.addWidget(QLabel("Category *"), 0, 4)
        layout.addWidget(self.category_combo, 0, 5)
        layout.addWidget(QLabel("Library source"), 1, 0)
        layout.addWidget(self.hazard_type_combo, 1, 1, 1, 3)
        layout.addWidget(self.copy_library_button, 1, 4)
        layout.addWidget(self.source_summary_label, 2, 1, 1, 5)
        return header

    def _build_hazard_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        what_group = QGroupBox("What Is It?")
        what_layout = QVBoxLayout(what_group)
        self.description_edit = QPlainTextEdit()
        self.description_edit.setPlaceholderText("Describe the hazard as it exists in this incident.")
        self.description_edit.setMinimumHeight(160)
        what_layout.addWidget(self.description_edit)
        layout.addWidget(what_group)

        location_group = QGroupBox("Location / Area")
        location_layout = QVBoxLayout(location_group)
        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("e.g., Division A / North Ridge / Staging Area")
        location_layout.addWidget(self.location_edit)
        layout.addWidget(location_group)

        layout.addStretch(1)
        return tab

    def _build_safety_content_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        top = QHBoxLayout()
        controls_group = QGroupBox("Mitigation Controls")
        controls_layout = QVBoxLayout(controls_group)
        controls_layout.addWidget(QLabel("Incident-specific controls used to reduce this hazard."))
        self.controls_editor = StringListEditor(
            placeholder="Add a mitigation control",
            empty_message="Enter a mitigation control first.",
            add_button_text="Add Control",
            remove_button_text="Remove Selected",
        )
        controls_layout.addWidget(self.controls_editor)
        top.addWidget(controls_group, 1)

        ppe_group = QGroupBox("PPE")
        ppe_layout = QVBoxLayout(ppe_group)
        ppe_layout.addWidget(QLabel("PPE required or recommended for this incident hazard."))
        self.ppe_editor = StringListEditor(
            placeholder="Add a PPE item",
            empty_message="Enter a PPE item first.",
            add_button_text="Add PPE",
            remove_button_text="Remove Selected",
        )
        ppe_layout.addWidget(self.ppe_editor)
        top.addWidget(ppe_group, 1)
        layout.addLayout(top, 2)

        language_group = QGroupBox("Standard Safety Language")
        language_layout = QVBoxLayout(language_group)
        self.safety_language_edit = QPlainTextEdit()
        self.safety_language_edit.setPlaceholderText("Briefing/form language for this hazard.")
        self.safety_language_edit.setMinimumHeight(150)
        language_layout.addWidget(self.safety_language_edit)
        layout.addWidget(language_group, 1)
        return tab

    def _build_spe_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        intro = QLabel(
            "Initial SPE captures the hazard before mitigations. Residual SPE captures the expected risk after controls are applied."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        spe_row = QHBoxLayout()
        self.default_spe = SpeAssessmentEditor("Initial SPE", assessed=True)
        self.spe_residual = SpeAssessmentEditor("Residual SPE", assessed=False)
        spe_row.addWidget(self.default_spe, 1)
        spe_row.addWidget(self.spe_residual, 1)
        layout.addLayout(spe_row, 1)
        return tab

    def _build_links_tab(self, default_op_period: object) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        top = QHBoxLayout()
        op_group = QGroupBox("Operational Periods")
        op_layout = QVBoxLayout(op_group)
        self.op_periods_list = CheckableList(
            [{"id": i} for i in range(1, 21)],
            "id",
            lambda d: str(d["id"]),
            self._normalize_default_op_period_ids(default_op_period),
            show_filter=False,
        )
        self.op_periods_list.setMaximumHeight(140)
        op_layout.addWidget(self.op_periods_list)
        top.addWidget(op_group, 1)

        zones_group = QGroupBox("Hazard Zones")
        zones_layout = QVBoxLayout(zones_group)
        self.hazard_zones_list = CheckableList(
            _fetch_hazard_zones(self._incident_id),
            "id",
            lambda d: d.get("label") or d.get("name") or f"Hazard Zone {d.get('id')}",
            set(),
        )
        zones_layout.addWidget(self.hazard_zones_list)
        top.addWidget(zones_group, 1)
        layout.addLayout(top, 1)

        linked_group = QGroupBox("Work Assignments, Teams, And Tasks")
        linked_layout = QVBoxLayout(linked_group)
        self.link_summary_label = QLabel("No linked work assignments, teams, or tasks.")
        self.link_summary_label.setWordWrap(True)
        self.link_button = QPushButton("Select Linked Items")
        self.link_button.clicked.connect(self._open_link_picker)
        linked_layout.addWidget(self.link_summary_label)
        linked_layout.addWidget(self.link_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(linked_group)
        return tab

    def _build_notes_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        notes_group = QGroupBox("Incident Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Internal notes specific to this incident hazard.")
        self.notes_edit.setMinimumHeight(180)
        notes_layout.addWidget(self.notes_edit)
        layout.addWidget(notes_group, 1)

        metadata_group = QGroupBox("Read-Only Metadata")
        metadata_layout = QGridLayout(metadata_group)
        self.source_label = QLabel("Incident-only hazard")
        self.library_id_label = QLabel("None")
        self.created_label = QLabel("")
        self.updated_label = QLabel("")
        metadata_layout.addWidget(QLabel("Source"), 0, 0)
        metadata_layout.addWidget(self.source_label, 0, 1)
        metadata_layout.addWidget(QLabel("Library hazard type id"), 1, 0)
        metadata_layout.addWidget(self.library_id_label, 1, 1)
        metadata_layout.addWidget(QLabel("Created"), 2, 0)
        metadata_layout.addWidget(self.created_label, 2, 1)
        metadata_layout.addWidget(QLabel("Updated"), 3, 0)
        metadata_layout.addWidget(self.updated_label, 3, 1)
        layout.addWidget(metadata_group)
        return tab

    def _selected_library_hazard(self) -> Optional[dict[str, Any]]:
        hazard_type = self.hazard_type_combo.currentData()
        return dict(hazard_type) if hazard_type else None

    def _copy_selected_library_hazard(self) -> None:
        hazard_type = self._selected_library_hazard()
        if not hazard_type:
            QMessageBox.information(self, "Hazard Library", "Select a library hazard first.")
            return
        self.title_edit.setText(str(hazard_type.get("name") or ""))
        self.category_combo.setCurrentText(str(hazard_type.get("category") or HAZARD_CATEGORIES[-1]))
        self.description_edit.setPlainText(str(hazard_type.get("description") or ""))
        self.controls_editor.set_items([str(value) for value in hazard_type.get("controls") or []])
        self.ppe_editor.set_items([str(value) for value in hazard_type.get("ppe") or []])
        self.safety_language_edit.setPlainText(str(hazard_type.get("standard_safety_language") or ""))
        self.default_spe.set_value(hazard_type.get("default_spe"))
        self._update_source_summary()

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
            self.link_summary_label.setText("No linked work assignments, teams, or tasks.")
        else:
            self.link_summary_label.setText(
                f"{len(self._links['work_assignment_ids'])} work assignment(s), "
                f"{len(self._links['team_ids'])} team(s), "
                f"{len(self._links['task_ids'])} task(s)"
            )

    def _update_source_summary(self, *_args) -> None:
        hazard_type = self._selected_library_hazard()
        if hazard_type:
            source_text = f"Library copy: {hazard_type.get('name') or 'Selected hazard'}"
            library_id = str(hazard_type.get("id") or "None")
        else:
            source_text = "Incident-only hazard"
            library_id = "None"
        self.source_summary_label.setText(source_text)
        self.source_label.setText(source_text)
        self.library_id_label.setText(library_id)

    def _set_hazard_type_combo(self, hazard_type_id: object) -> None:
        if not hazard_type_id:
            self.hazard_type_combo.setCurrentIndex(0)
            return
        for index in range(self.hazard_type_combo.count()):
            item = self.hazard_type_combo.itemData(index)
            if item and str(item.get("id")) == str(hazard_type_id):
                self.hazard_type_combo.setCurrentIndex(index)
                return
        self.hazard_type_combo.setCurrentIndex(0)

    def _set_checked_ids(self, checkable_list: CheckableList, selected_ids: set[int]) -> None:
        for row in range(checkable_list.list_widget.count()):
            item = checkable_list.list_widget.item(row)
            item_id = int(item.data(Qt.ItemDataRole.UserRole))
            item.setCheckState(Qt.CheckState.Checked if item_id in selected_ids else Qt.CheckState.Unchecked)

    def _populate(self, hazard: dict) -> None:
        self.title_edit.setText(hazard.get("title", ""))
        self.description_edit.setPlainText(hazard.get("description") or "")
        self.category_combo.setCurrentText(hazard.get("category") or HAZARD_CATEGORIES[-1])
        self._set_hazard_type_combo(hazard.get("hazard_type_id"))
        self._update_source_summary()
        self.location_edit.setText(hazard.get("location_text") or "")
        self._set_checked_ids(self.op_periods_list, {int(value) for value in hazard.get("op_period_ids") or []})
        self._set_checked_ids(self.hazard_zones_list, {int(value) for value in hazard.get("hazard_zone_ids") or []})

        links = hazard.get("links") or {}
        self._links = {
            "work_assignment_ids": list(links.get("work_assignment_ids") or []),
            "team_ids": list(links.get("team_ids") or []),
            "task_ids": list(links.get("task_ids") or []),
        }
        self._update_link_summary()

        self.controls_editor.set_items(_split_lines(hazard.get("control_measure") or ""))
        self.ppe_editor.set_items(_split_lines(hazard.get("ppe_text") or ""))
        self.safety_language_edit.setPlainText(
            hazard.get("safety_message") or hazard.get("mitigation_text") or ""
        )
        self.notes_edit.setPlainText(hazard.get("notes") or "")
        self.default_spe.set_value(hazard.get("default_spe"))
        self.spe_residual.set_value(hazard.get("spe_residual"))

        self.created_label.setText(hazard.get("created_at") or "")
        self.updated_label.setText(hazard.get("updated_at") or "")

    def _attempt_save(self) -> None:
        title = self.title_edit.text().strip()
        category = self.category_combo.currentText().strip()
        errors = []
        if not title:
            errors.append("Hazard name is required.")
        if not category:
            errors.append("Category is required.")
        if errors:
            self._error_label.setText(" ".join(errors))
            self._error_label.show()
            QMessageBox.warning(self, "Validation", "\n".join(errors))
            return

        hazard_type = self._selected_library_hazard()
        safety_language = self.safety_language_edit.toPlainText().strip() or None
        self._result = {
            "title": title,
            "description": self.description_edit.toPlainText().strip() or None,
            "category": category or None,
            "hazard_type_id": str(hazard_type["id"]) if hazard_type else None,
            "hazard_type_text": hazard_type.get("name") if hazard_type else None,
            "op_period_ids": self.op_periods_list.selected_ids(),
            "hazard_zone_ids": self.hazard_zones_list.selected_ids(),
            "location_text": self.location_edit.text().strip() or None,
            "links": self._links,
            "control_measure": "\n".join(self.controls_editor.items()) or None,
            "mitigation_text": safety_language,
            "ppe_text": "\n".join(self.ppe_editor.items()) or None,
            "safety_message": safety_language,
            "notes": self.notes_edit.toPlainText().strip() or None,
            "default_spe": self.default_spe.value(),
            "spe_residual": self.spe_residual.value(),
        }
        self.accept()

    def result_payload(self) -> Optional[dict[str, Any]]:
        return self._result
