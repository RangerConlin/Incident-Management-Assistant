"""Filter sidebar for the communications traffic log."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from PySide6.QtCore import Qt, QDateTime, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from ..models import CommsLogFilterPreset, CommsLogQuery


class LogFilterPanel(QWidget):
    """Sidebar widget holding filter controls and preset management."""

    filtersChanged = Signal(object)
    presetSaveRequested = Signal(str, dict)
    presetDeleteRequested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)

        self.start_enabled = QCheckBox("Start")
        self.start_edit = QDateTimeEdit(QDateTime.currentDateTime())
        self.start_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.start_edit.setCalendarPopup(True)
        start_row = QHBoxLayout()
        start_row.addWidget(self.start_enabled)
        start_row.addWidget(self.start_edit)
        form.addRow(start_row)

        self.end_enabled = QCheckBox("End")
        self.end_edit = QDateTimeEdit(QDateTime.currentDateTime())
        self.end_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.end_edit.setCalendarPopup(True)
        end_row = QHBoxLayout()
        end_row.addWidget(self.end_enabled)
        end_row.addWidget(self.end_edit)
        form.addRow(end_row)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["Any", "Routine", "Priority", "Emergency"])
        form.addRow("Priority", self.priority_combo)

        self.channel_combo = QComboBox()
        self.channel_combo.setEditable(True)
        self.channel_combo.addItem("Any", None)
        form.addRow("Channel", self.channel_combo)

        self.unit_field = QLineEdit()
        form.addRow("Unit/Callsign", self.unit_field)

        self.operator_field = QLineEdit()
        form.addRow("Operator", self.operator_field)

        self.disposition_combo = QComboBox()
        self.disposition_combo.addItems(["Any", "Open", "Closed"])
        form.addRow("Disposition", self.disposition_combo)

        self.attachments_combo = QComboBox()
        self.attachments_combo.addItems(["Any", "Yes", "No"])
        form.addRow("Attachments", self.attachments_combo)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["Any", "Status Updates", "Non Status"])
        form.addRow("Status", self.status_combo)

        self.follow_combo = QComboBox()
        self.follow_combo.addItems(["Any", "Requires Follow-up", "No Follow-up"])
        form.addRow("Follow-up", self.follow_combo)

        self.notification_field = QLineEdit()
        form.addRow("Notification", self.notification_field)

        self.text_field = QLineEdit()
        form.addRow("Search", self.text_field)

        layout.addLayout(form)

        clear_btn = QPushButton("Clear Filters")
        clear_btn.clicked.connect(self.reset_filters)
        layout.addWidget(clear_btn)

        layout.addWidget(QLabel("Saved Presets"))
        self.preset_list = QListWidget()
        self.preset_list.itemDoubleClicked.connect(self._apply_selected_preset)
        layout.addWidget(self.preset_list, 1)

        preset_buttons = QHBoxLayout()
        self.save_button = QPushButton("Save Preset")
        self.save_button.clicked.connect(self._on_save_clicked)
        preset_buttons.addWidget(self.save_button)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self._on_delete_clicked)
        preset_buttons.addWidget(self.delete_button)
        layout.addLayout(preset_buttons)

        layout.addSpacerItem(QSpacerItem(1, 1))

        # Connect change signals to re-emit filter updates
        self.start_enabled.toggled.connect(self._emit_filters)
        self.start_edit.dateTimeChanged.connect(self._emit_filters)
        self.end_enabled.toggled.connect(self._emit_filters)
        self.end_edit.dateTimeChanged.connect(self._emit_filters)
        self.priority_combo.currentIndexChanged.connect(self._emit_filters)
        self.channel_combo.currentIndexChanged.connect(self._emit_filters)
        self.unit_field.textChanged.connect(self._emit_filters)
        self.operator_field.textChanged.connect(self._emit_filters)
        self.disposition_combo.currentIndexChanged.connect(self._emit_filters)
        self.attachments_combo.currentIndexChanged.connect(self._emit_filters)
        self.status_combo.currentIndexChanged.connect(self._emit_filters)
        self.follow_combo.currentIndexChanged.connect(self._emit_filters)
        self.notification_field.textChanged.connect(self._emit_filters)
        self.text_field.textChanged.connect(self._emit_filters)

    # ------------------------------------------------------------------
    # Filter management
    # ------------------------------------------------------------------
    def current_query(self) -> CommsLogQuery:
        query = CommsLogQuery()
        if self.start_enabled.isChecked():
            query.start_ts_utc = self.start_edit.dateTime().toUTC().toString(Qt.ISODate)
        if self.end_enabled.isChecked():
            query.end_ts_utc = self.end_edit.dateTime().toUTC().toString(Qt.ISODate)
        if self.priority_combo.currentIndex() > 0:
            query.priorities = [self.priority_combo.currentText()]
        if self.channel_combo.currentData():
            query.resource_ids = [self.channel_combo.currentData()]
        elif self.channel_combo.currentText() and self.channel_combo.currentIndex() == -1:
            query.resource_labels = [self.channel_combo.currentText()]
        if self.unit_field.text().strip():
            query.unit_like = self.unit_field.text().strip()
        if self.operator_field.text().strip():
            query.operator_ids = [self.operator_field.text().strip()]
        if self.disposition_combo.currentIndex() > 0:
            query.dispositions = [self.disposition_combo.currentText()]
        attachments_idx = self.attachments_combo.currentIndex()
        if attachments_idx == 1:
            query.has_attachments = True
        elif attachments_idx == 2:
            query.has_attachments = False
        status_idx = self.status_combo.currentIndex()
        if status_idx == 1:
            query.is_status_update = True
        elif status_idx == 2:
            query.is_status_update = False
        follow_idx = self.follow_combo.currentIndex()
        if follow_idx == 1:
            query.follow_up_required = True
        elif follow_idx == 2:
            query.follow_up_required = False
        if self.notification_field.text().strip():
            query.notification_levels = [self.notification_field.text().strip()]
        if self.text_field.text().strip():
            query.text_search = self.text_field.text().strip()
        return query

    def reset_filters(self) -> None:
        self.start_enabled.setChecked(False)
        self.end_enabled.setChecked(False)
        self.priority_combo.setCurrentIndex(0)
        self.channel_combo.setCurrentIndex(0)
        self.channel_combo.setEditText("")
        self.unit_field.clear()
        self.operator_field.clear()
        self.disposition_combo.setCurrentIndex(0)
        self.attachments_combo.setCurrentIndex(0)
        self.status_combo.setCurrentIndex(0)
        self.follow_combo.setCurrentIndex(0)
        self.notification_field.clear()
        self.text_field.clear()
        self._emit_filters()

    def populate_channels(self, channels: Iterable[Dict[str, object]]) -> None:
        current = self.channel_combo.currentData()
        text = self.channel_combo.currentText()
        self.channel_combo.blockSignals(True)
        self.channel_combo.clear()
        self.channel_combo.addItem("Any", None)
        for channel in channels:
            label = str(channel.get("display_name") or channel.get("name") or "")
            self.channel_combo.addItem(label, channel.get("id"))
        if current:
            idx = self.channel_combo.findData(current)
            if idx >= 0:
                self.channel_combo.setCurrentIndex(idx)
            else:
                self.channel_combo.setEditText(text)
        self.channel_combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Preset helpers
    # ------------------------------------------------------------------
    def populate_presets(self, presets: Iterable[CommsLogFilterPreset]) -> None:
        self.preset_list.clear()
        for preset in presets:
            item = QListWidgetItem(preset.name)
            item.setData(Qt.UserRole, preset)
            self.preset_list.addItem(item)

    def _on_save_clicked(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Filter Preset", "Preset name:")
        if not ok or not name.strip():
            return
        filters = {k: v for k, v in self.current_query().__dict__.items() if v not in (None, [], "")}
        self.presetSaveRequested.emit(name.strip(), filters)

    def _on_delete_clicked(self) -> None:
        item = self.preset_list.currentItem()
        if not item:
            return
        preset = item.data(Qt.UserRole)
        if preset and getattr(preset, "id", None):
            self.presetDeleteRequested.emit(int(preset.id))

    def _apply_selected_preset(self, item: QListWidgetItem) -> None:
        preset = item.data(Qt.UserRole)
        if not preset:
            return
        filters = getattr(preset, "filters", {}) or {}
        self.apply_filters(filters)

    def apply_filters(self, filters: Dict[str, object]) -> None:
        self.start_enabled.setChecked(bool(filters.get("start_ts_utc")))
        if filters.get("start_ts_utc"):
            self.start_edit.setDateTime(QDateTime.fromString(str(filters["start_ts_utc"]), Qt.ISODate))
        self.end_enabled.setChecked(bool(filters.get("end_ts_utc")))
        if filters.get("end_ts_utc"):
            self.end_edit.setDateTime(QDateTime.fromString(str(filters["end_ts_utc"]), Qt.ISODate))
        self._set_combo_value(self.priority_combo, filters.get("priorities"))
        if filters.get("resource_ids"):
            value = filters["resource_ids"][0]
            idx = self.channel_combo.findData(value)
            if idx >= 0:
                self.channel_combo.setCurrentIndex(idx)
        elif filters.get("resource_labels"):
            self.channel_combo.setEditText(str(filters["resource_labels"][0]))
        else:
            self.channel_combo.setCurrentIndex(0)
            self.channel_combo.setEditText("")
        self.unit_field.setText(str(filters.get("unit_like") or ""))
        if filters.get("operator_ids"):
            self.operator_field.setText(str(filters["operator_ids"][0]))
        else:
            self.operator_field.clear()
        self._set_combo_value(self.disposition_combo, filters.get("dispositions"))
        self._set_combo_bool_combo(self.attachments_combo, filters.get("has_attachments"))
        self._set_combo_bool_combo(self.status_combo, filters.get("is_status_update"))
        self._set_combo_bool_combo(self.follow_combo, filters.get("follow_up_required"))
        if filters.get("notification_levels"):
            self.notification_field.setText(str(filters["notification_levels"][0]))
        else:
            self.notification_field.clear()
        self.text_field.setText(str(filters.get("text_search") or ""))
        self._emit_filters()

    def _set_combo_value(self, combo: QComboBox, values: Optional[List[str]]) -> None:
        if values:
            value = values[0]
            idx = combo.findText(value)
            if idx >= 0:
                combo.setCurrentIndex(idx)
                return
        combo.setCurrentIndex(0)

    def _set_combo_bool_combo(self, combo: QComboBox, value: Optional[bool]) -> None:
        if value is True:
            combo.setCurrentIndex(1)
        elif value is False:
            combo.setCurrentIndex(2)
        else:
            combo.setCurrentIndex(0)

    # ------------------------------------------------------------------
    def _emit_filters(self) -> None:
        self.filtersChanged.emit(self.current_query())


__all__ = ["LogFilterPanel"]
