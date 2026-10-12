"""Shared hazard type detail form and dialog."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from modules.safety.orm.scoring import spe_band, spe_score

from ..data.hazard_type_repository import ApiHazardTypeRepository
from ..models.hazard_type_models import (
    EXPOSURE_OPTIONS,
    HAZARD_CATEGORIES,
    PROBABILITY_OPTIONS,
    SEVERITY_OPTIONS,
    HazardDefaultSpe,
    HazardType,
)


def _split_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


class StringListEditor(QWidget):
    """Simple add/remove editor for a string collection."""

    changed = Signal()

    def __init__(
        self,
        *,
        placeholder: str,
        empty_message: str,
        add_button_text: str,
        remove_button_text: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._empty_message = empty_message

        self._list = QListWidget()
        self._input = QLineEdit()
        self._input.setPlaceholderText(placeholder)
        add_button = QPushButton(add_button_text)
        remove_button = QPushButton(remove_button_text)

        add_button.clicked.connect(self._add_item)
        remove_button.clicked.connect(self._remove_selected)
        self._input.returnPressed.connect(self._add_item)
        self._list.model().rowsInserted.connect(lambda *_: self.changed.emit())
        self._list.model().rowsRemoved.connect(lambda *_: self.changed.emit())

        controls = QHBoxLayout()
        controls.addWidget(self._input, 1)
        controls.addWidget(add_button)
        controls.addWidget(remove_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(controls)
        layout.addWidget(self._list)

    def set_items(self, values: list[str]) -> None:
        self._list.clear()
        for value in values:
            if value.strip():
                self._list.addItem(value.strip())

    def items(self) -> list[str]:
        values: list[str] = []
        for index in range(self._list.count()):
            value = self._list.item(index).text().strip()
            if value:
                values.append(value)
        return values

    def _add_item(self) -> None:
        value = self._input.text().strip()
        if not value:
            QMessageBox.information(self, "Add Item", self._empty_message)
            return
        existing = {self._list.item(index).text().strip().lower() for index in range(self._list.count())}
        if value.lower() in existing:
            QMessageBox.information(self, "Add Item", "That entry is already listed.")
            return
        self._list.addItem(value)
        self._input.clear()
        self.changed.emit()

    def _remove_selected(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)
            self.changed.emit()


class HazardTypeDetailForm(QWidget):
    """Editable detail form used both inline and in the modal dialog."""

    changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._hazard_type: Optional[HazardType] = None
        self._building = False

        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)
        root.addWidget(self._build_identity_group())
        root.addWidget(self._build_aliases_group())
        root.addWidget(self._build_controls_group())
        root.addWidget(self._build_ppe_group())
        root.addWidget(self._build_safety_language_group())
        root.addWidget(self._build_spe_group())
        root.addWidget(self._build_audit_group())
        root.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

        self._bind_change_tracking()
        self.set_hazard_type(None)

    def _build_identity_group(self) -> QGroupBox:
        group = QGroupBox("Identity")
        form = QFormLayout(group)

        self.name_edit = QLineEdit()
        self.category_combo = QComboBox()
        self.category_combo.addItems(HAZARD_CATEGORIES)
        self.active_combo = QComboBox()
        self.active_combo.addItem("Active", True)
        self.active_combo.addItem("Archived", False)
        self.description_edit = QPlainTextEdit()
        self.description_edit.setPlaceholderText("Describe what the hazard is and where it commonly shows up.")
        self.description_edit.setMinimumHeight(90)

        form.addRow("Hazard name *", self.name_edit)
        form.addRow("Category *", self.category_combo)
        form.addRow("Status", self.active_combo)
        form.addRow("Description", self.description_edit)
        return group

    def _build_aliases_group(self) -> QGroupBox:
        group = QGroupBox("Aliases")
        layout = QVBoxLayout(group)
        layout.addWidget(QLabel("Aliases improve search and let field users find the same hazard by local wording."))
        self.aliases_editor = StringListEditor(
            placeholder="Add another name users might search for",
            empty_message="Enter an alias first.",
            add_button_text="Add Alias",
            remove_button_text="Remove Selected",
        )
        layout.addWidget(self.aliases_editor)
        return group

    def _build_controls_group(self) -> QGroupBox:
        group = QGroupBox("Mitigation Controls")
        layout = QVBoxLayout(group)
        layout.addWidget(QLabel("Store the standard control measures that should copy into incident hazards by default."))
        self.controls_editor = StringListEditor(
            placeholder="Add a mitigation control",
            empty_message="Enter a mitigation control first.",
            add_button_text="Add Control",
            remove_button_text="Remove Selected",
        )
        layout.addWidget(self.controls_editor)
        return group

    def _build_ppe_group(self) -> QGroupBox:
        group = QGroupBox("PPE")
        layout = QVBoxLayout(group)
        layout.addWidget(QLabel("List the standard PPE items this hazard usually requires or recommends."))
        self.ppe_editor = StringListEditor(
            placeholder="Add a PPE item",
            empty_message="Enter a PPE item first.",
            add_button_text="Add PPE",
            remove_button_text="Remove Selected",
        )
        layout.addWidget(self.ppe_editor)
        return group

    def _build_safety_language_group(self) -> QGroupBox:
        group = QGroupBox("Standard Safety Language")
        layout = QVBoxLayout(group)
        self.safety_language_edit = QPlainTextEdit()
        self.safety_language_edit.setPlaceholderText("Standard wording for briefings, worksheets, and incident safety messaging.")
        self.safety_language_edit.setMinimumHeight(110)
        layout.addWidget(self.safety_language_edit)
        return group

    def _build_spe_group(self) -> QGroupBox:
        group = QGroupBox("Default SPE")
        layout = QVBoxLayout(group)

        intro = QLabel(
            "Set the default Severity, Probability, and Exposure values used when this hazard is copied into an incident."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        selectors = QGridLayout()
        self.severity_combo = QComboBox()
        self.probability_combo = QComboBox()
        self.exposure_combo = QComboBox()
        self._load_option_items(self.severity_combo, SEVERITY_OPTIONS)
        self._load_option_items(self.probability_combo, PROBABILITY_OPTIONS)
        self._load_option_items(self.exposure_combo, EXPOSURE_OPTIONS)
        selectors.addWidget(QLabel("Severity (1-5)"), 0, 0)
        selectors.addWidget(QLabel("Probability (1-5)"), 0, 1)
        selectors.addWidget(QLabel("Exposure (1-4)"), 0, 2)
        selectors.addWidget(self.severity_combo, 1, 0)
        selectors.addWidget(self.probability_combo, 1, 1)
        selectors.addWidget(self.exposure_combo, 1, 2)
        layout.addLayout(selectors)

        results_row = QHBoxLayout()
        score_frame, self.score_value = self._create_result_frame("Score")
        band_frame, self.band_value = self._create_result_frame("Band")
        action_frame, self.action_value = self._create_result_frame("Action")
        results_row.addWidget(score_frame)
        results_row.addWidget(band_frame)
        results_row.addWidget(action_frame)
        layout.addLayout(results_row)

        definitions = QGridLayout()
        definitions.addWidget(self._build_definition_box(
            "Severity",
            "Potential consequences measured in damage, injury, or incident impact.",
            SEVERITY_OPTIONS,
        ), 0, 0)
        definitions.addWidget(self._build_definition_box(
            "Probability",
            "Likelihood that the potential consequences will occur.",
            PROBABILITY_OPTIONS,
        ), 0, 1)
        definitions.addWidget(self._build_definition_box(
            "Exposure",
            "Amount of time, repetition, people, or equipment involved.",
            EXPOSURE_OPTIONS,
        ), 0, 2)
        layout.addLayout(definitions)
        return group

    def _build_audit_group(self) -> QGroupBox:
        group = QGroupBox("Audit")
        form = QFormLayout(group)
        self.created_at_label = QLabel("Saved after creation")
        self.updated_at_label = QLabel("Saved after creation")
        self.created_by_label = QLabel("")
        self.updated_by_label = QLabel("")
        form.addRow("Created at", self.created_at_label)
        form.addRow("Updated at", self.updated_at_label)
        form.addRow("Created by", self.created_by_label)
        form.addRow("Updated by", self.updated_by_label)
        return group

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
        scale_lines = [f"{value} = {label}" for value, label in options]
        scale = QLabel("\n".join(scale_lines))
        scale.setWordWrap(True)
        scale.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(scale)
        return frame

    def _bind_change_tracking(self) -> None:
        self.name_edit.textChanged.connect(self._emit_change)
        self.category_combo.currentIndexChanged.connect(self._emit_change)
        self.active_combo.currentIndexChanged.connect(self._emit_change)
        self.description_edit.textChanged.connect(self._emit_change)
        self.safety_language_edit.textChanged.connect(self._emit_change)
        self.aliases_editor.changed.connect(self._emit_change)
        self.controls_editor.changed.connect(self._emit_change)
        self.ppe_editor.changed.connect(self._emit_change)
        self.severity_combo.currentIndexChanged.connect(self._on_spe_changed)
        self.probability_combo.currentIndexChanged.connect(self._on_spe_changed)
        self.exposure_combo.currentIndexChanged.connect(self._on_spe_changed)

    def _emit_change(self) -> None:
        if not self._building:
            self.changed.emit()

    def _on_spe_changed(self) -> None:
        self._update_spe_outputs()
        self._emit_change()

    def _current_combo_value(self, combo: QComboBox) -> int:
        data = combo.currentData()
        return int(data) if data is not None else 1

    def _set_combo_value(self, combo: QComboBox, value: int) -> None:
        for index in range(combo.count()):
            if int(combo.itemData(index)) == int(value):
                combo.setCurrentIndex(index)
                return
        combo.setCurrentIndex(0)

    def _update_spe_outputs(self) -> None:
        severity = self._current_combo_value(self.severity_combo)
        probability = self._current_combo_value(self.probability_combo)
        exposure = self._current_combo_value(self.exposure_combo)
        score = spe_score(severity, probability, exposure)
        band, action = spe_band(score)
        self.score_value.setText(str(score))
        self.band_value.setText(band)
        self.action_value.setText(action)

    def set_hazard_type(self, hazard_type: Optional[HazardType]) -> None:
        self._building = True
        self._hazard_type = hazard_type
        record = hazard_type or HazardType(name="")

        self.name_edit.setText(record.name)
        self.category_combo.setCurrentText(record.category or HAZARD_CATEGORIES[-1])
        self.active_combo.setCurrentIndex(0 if record.active else 1)
        self.description_edit.setPlainText(record.description)
        self.aliases_editor.set_items(record.aliases)
        self.controls_editor.set_items(record.controls)
        self.ppe_editor.set_items(record.ppe)
        self.safety_language_edit.setPlainText(record.standard_safety_language)

        default_spe = record.default_spe or HazardDefaultSpe(
            severity=1,
            probability=1,
            exposure=1,
            score=1,
            band="Slight",
            action="Possibly Acceptable",
        )
        self._set_combo_value(self.severity_combo, default_spe.severity)
        self._set_combo_value(self.probability_combo, default_spe.probability)
        self._set_combo_value(self.exposure_combo, default_spe.exposure)
        self._update_spe_outputs()

        self.created_at_label.setText(record.created_at or "Saved after creation")
        self.updated_at_label.setText(record.updated_at or "Saved after creation")
        self.created_by_label.setText(record.created_by or "")
        self.updated_by_label.setText(record.updated_by or "")
        self._building = False

    def validate(self) -> bool:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Hazard Type", "Hazard name is required.")
            return False
        if not self.category_combo.currentText().strip():
            QMessageBox.warning(self, "Hazard Type", "Category is required.")
            return False
        return True

    def to_model(self) -> HazardType:
        severity = self._current_combo_value(self.severity_combo)
        probability = self._current_combo_value(self.probability_combo)
        exposure = self._current_combo_value(self.exposure_combo)
        score = spe_score(severity, probability, exposure)
        band, action = spe_band(score)
        return HazardType(
            id=self._hazard_type.id if self._hazard_type else None,
            name=self.name_edit.text().strip(),
            category=self.category_combo.currentText().strip() or HAZARD_CATEGORIES[-1],
            description=self.description_edit.toPlainText().strip(),
            aliases=self.aliases_editor.items(),
            controls=self.controls_editor.items(),
            ppe=self.ppe_editor.items(),
            standard_safety_language=self.safety_language_edit.toPlainText().strip(),
            default_spe=HazardDefaultSpe(
                severity=severity,
                probability=probability,
                exposure=exposure,
                score=score,
                band=band,
                action=action,
            ),
            active=bool(self.active_combo.currentData()),
            created_at=self._hazard_type.created_at if self._hazard_type else "",
            updated_at=self._hazard_type.updated_at if self._hazard_type else "",
            created_by=self._hazard_type.created_by if self._hazard_type else "",
            updated_by=self._hazard_type.updated_by if self._hazard_type else "",
        )

    def set_read_only(self, read_only: bool) -> None:
        self.name_edit.setReadOnly(read_only)
        self.category_combo.setEnabled(not read_only)
        self.active_combo.setEnabled(not read_only)
        self.description_edit.setReadOnly(read_only)
        self.safety_language_edit.setReadOnly(read_only)
        self.aliases_editor.setEnabled(not read_only)
        self.controls_editor.setEnabled(not read_only)
        self.ppe_editor.setEnabled(not read_only)
        self.severity_combo.setEnabled(not read_only)
        self.probability_combo.setEnabled(not read_only)
        self.exposure_combo.setEnabled(not read_only)


class HazardTypeEditorWindow(QDialog):
    """Modal wrapper kept for compatibility with existing callers."""

    def __init__(
        self,
        repository: ApiHazardTypeRepository,
        hazard_type: Optional[HazardType] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.setWindowTitle("Edit Hazard Type" if hazard_type else "New Hazard Type")
        self.resize(900, 760)

        self.form = HazardTypeDetailForm(self)
        self.form.set_hazard_type(hazard_type)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.form)
        layout.addWidget(buttons)

    def to_model(self) -> HazardType:
        return self.form.to_model()

    def _accept_save(self) -> None:
        if self.form.validate():
            self.accept()
