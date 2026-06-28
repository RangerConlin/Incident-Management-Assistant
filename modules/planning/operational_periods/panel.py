from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
    QDateTimeEdit,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .repository import OperationalPeriodRecord, OperationalPeriodRepository
from utils.table_view_styles import apply_statusboard_table_behavior

# Status -> (row background, badge background, badge text) — light and dark variants
_STATUS_COLORS_LIGHT: dict[str, tuple[str, str, str]] = {
    "Active":   ("#d4edda", "#28a745", "#ffffff"),
    "Planned":  ("#ffffff", "#e8eef5", "#333333"),
    "Complete": ("#f0f0f0", "#6c757d", "#ffffff"),
    "Canceled": ("#fff3f3", "#dc3545", "#ffffff"),
}
_STATUS_COLORS_DARK: dict[str, tuple[str, str, str]] = {
    "Active":   ("#1a3a28", "#4caf50", "#ffffff"),
    "Planned":  ("#1B1F2A", "#5CA3FF", "#ECEFF4"),
    "Complete": ("#1a1c22", "#888888", "#ffffff"),
    "Canceled": ("#3a1a1a", "#ef5350", "#ffffff"),
}
# Active row text colors per mode
_ACTIVE_ROW_FG_LIGHT = "#155724"
_ACTIVE_ROW_FG_DARK  = "#a5d6a7"
_COMPLETE_ROW_FG_LIGHT = "#6c757d"
_COMPLETE_ROW_FG_DARK  = "#888888"


def _is_dark_mode() -> bool:
    palette = QApplication.palette()
    return palette.color(QPalette.Window).lightness() < 128


def _status_colors() -> dict[str, tuple[str, str, str]]:
    return _STATUS_COLORS_DARK if _is_dark_mode() else _STATUS_COLORS_LIGHT


def _parse_storage_dt(value: str) -> datetime:
    if value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(value.replace(" ", "T"))
        except ValueError:
            pass
    return datetime.now().replace(second=0, microsecond=0)


def _storage_dt(value: QDateTimeEdit) -> str:
    return value.dateTime().toString(Qt.ISODate)


def _friendly_dt(iso: str) -> str:
    """Return a compact human-readable datetime string."""
    if not iso:
        return "—"
    try:
        dt = _parse_storage_dt(iso)
        return dt.strftime("%b %d  %H:%M")
    except Exception:
        return iso


def _duration_label(start_iso: str, end_iso: str) -> str:
    """Return e.g. '12h' or '1d 6h' for the span between two ISO strings."""
    try:
        s = _parse_storage_dt(start_iso)
        e = _parse_storage_dt(end_iso)
        total_minutes = max(0, int((e - s).total_seconds() // 60))
        days, rem_min = divmod(total_minutes, 1440)
        hours, minutes = divmod(rem_min, 60)
        parts: list[str] = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes and not days:
            parts.append(f"{minutes}m")
        return " ".join(parts) if parts else "0h"
    except Exception:
        return "—"


class OperationalPeriodManagerPanel(QWidget):
    def __init__(self, incident_id: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.repository = OperationalPeriodRepository(incident_id=incident_id)
        self._periods: list[OperationalPeriodRecord] = []
        self._selected_period_id: int | None = None
        self._dirty = False
        self.setObjectName("OperationalPeriodManagerPanel")
        self.setWindowTitle("Planning - Operational Period Manager")
        self.resize(1000, 600)
        self._build_ui()
        self.refresh_all()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # Header row
        header = QHBoxLayout()
        title = QLabel("Operational Period Manager")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self._active_badge = QLabel("No active period")
        self._active_badge.setStyleSheet(
            "padding: 4px 10px; border-radius: 4px; font-weight: 600;"
        )
        header.addWidget(title)
        header.addWidget(self._active_badge)
        header.addStretch()

        new_btn = QPushButton("New Period")
        new_btn.clicked.connect(self._new_period)
        clone_btn = QPushButton("Clone Selected")
        clone_btn.clicked.connect(self._clone_selected)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_all)
        for btn in (new_btn, clone_btn, refresh_btn):
            header.addWidget(btn)
        root.addLayout(header)

        # Top: period list
        self.periods_table = QTableWidget(0, 5)
        self.periods_table.setHorizontalHeaderLabels(
            ["Period", "Status", "Start", "End", "Duration"]
        )
        apply_statusboard_table_behavior(self.periods_table)
        self.periods_table.setAlternatingRowColors(False)  # we paint rows manually
        self.periods_table.setFixedHeight(180)
        self.periods_table.itemSelectionChanged.connect(self._on_selection_changed)
        root.addWidget(self.periods_table)

        # Bottom: editor laid out in two columns
        editor_row = QHBoxLayout()
        root.addLayout(editor_row, 1)

        # Left column: period details + linked records
        left_col = QVBoxLayout()
        editor_row.addLayout(left_col, 1)

        basics_group = QGroupBox("Period Details")
        basics_form = QFormLayout(basics_group)
        basics_form.setHorizontalSpacing(12)
        basics_form.setVerticalSpacing(8)

        self.number_spin = QSpinBox()
        self.number_spin.setRange(1, 999)
        self.number_spin.valueChanged.connect(self._mark_dirty)

        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._mark_dirty)

        self.status_combo = QComboBox()
        self.status_combo.addItems(list(OperationalPeriodRepository.STATUSES))
        self.status_combo.currentTextChanged.connect(self._mark_dirty)

        self.start_edit = QDateTimeEdit()
        self.start_edit.setCalendarPopup(True)
        self.start_edit.setDisplayFormat("MM/dd/yyyy  HH:mm")
        self.start_edit.dateTimeChanged.connect(self._mark_dirty)

        self.end_edit = QDateTimeEdit()
        self.end_edit.setCalendarPopup(True)
        self.end_edit.setDisplayFormat("MM/dd/yyyy  HH:mm")
        self.end_edit.dateTimeChanged.connect(self._mark_dirty)

        duration_row = QHBoxLayout()
        duration_row.setSpacing(4)
        for hours in (12, 24, 48, 72):
            btn = QPushButton(f"{hours}h")
            btn.setToolTip(f"Set end time to {hours} hours after start")
            btn.clicked.connect(lambda _, h=hours: self._apply_duration(h))
            duration_row.addWidget(btn, 1)

        basics_form.addRow("Period Number", self.number_spin)
        basics_form.addRow("Label", self.name_edit)
        basics_form.addRow("Status", self.status_combo)
        basics_form.addRow("Start", self.start_edit)
        basics_form.addRow("End", self.end_edit)
        basics_form.addRow("", duration_row)
        left_col.addWidget(basics_group)

        summary_group = QGroupBox("Linked Records")
        summary_layout = QGridLayout(summary_group)
        self.summary_labels: dict[str, QLabel] = {}
        for idx, key in enumerate(("meetings", "assignments", "forms", "objectives")):
            label = QLabel("0")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-size: 20px; font-weight: 600; padding: 10px; background: palette(base);")
            self.summary_labels[key] = label
            summary_layout.addWidget(QLabel(key.replace("_", " ").title()), 0, idx)
            summary_layout.addWidget(label, 1, idx)
        left_col.addWidget(summary_group)
        left_col.addStretch()

        # Right column: notes + actions
        right_col = QVBoxLayout()
        editor_row.addLayout(right_col, 1)

        notes_group = QGroupBox("Operational Notes")
        notes_layout = QFormLayout(notes_group)
        notes_layout.setHorizontalSpacing(12)
        notes_layout.setVerticalSpacing(8)

        self.objectives_edit = QPlainTextEdit()
        self.objectives_edit.setPlaceholderText("Objectives, priorities, and carry-forward items.")
        self.objectives_edit.setFixedHeight(90)
        self.objectives_edit.textChanged.connect(self._mark_dirty)

        self.weather_edit = QPlainTextEdit()
        self.weather_edit.setPlaceholderText("Weather impacts and forecast notes.")
        self.weather_edit.setFixedHeight(70)
        self.weather_edit.textChanged.connect(self._mark_dirty)

        self.safety_edit = QPlainTextEdit()
        self.safety_edit.setPlaceholderText("Safety message, hazards, and controls.")
        self.safety_edit.setFixedHeight(70)
        self.safety_edit.textChanged.connect(self._mark_dirty)

        notes_layout.addRow("Objectives", self.objectives_edit)
        notes_layout.addRow("Weather", self.weather_edit)
        notes_layout.addRow("Safety", self.safety_edit)
        right_col.addWidget(notes_group, 1)

        actions = QHBoxLayout()
        actions.addStretch()
        self._set_active_btn = QPushButton("Set as Active Period")
        self._set_active_btn.clicked.connect(self._set_active_selected)
        self._save_btn = QPushButton("Save Period")
        self._save_btn.setDefault(True)
        self._save_btn.clicked.connect(self._save_selected)
        actions.addWidget(self._set_active_btn)
        actions.addWidget(self._save_btn)
        right_col.addLayout(actions)

    # ------------------------------------------------------------------
    # Dirty tracking
    # ------------------------------------------------------------------

    def _mark_dirty(self, *_) -> None:
        if not self._dirty:
            self._dirty = True
            self._save_btn.setText("Save Period  ●")

    def _apply_duration(self, hours: int) -> None:
        new_end = self.start_edit.dateTime().addSecs(hours * 3600)
        self.end_edit.setDateTime(new_end)

    def _clear_dirty(self) -> None:
        self._dirty = False
        self._save_btn.setText("Save Period")

    def _guard_dirty(self) -> bool:
        """Return True (safe to proceed) or False (user cancelled)."""
        if not self._dirty:
            return True
        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            "You have unsaved changes. Discard them?",
            QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        return reply == QMessageBox.Discard

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def refresh_all(self) -> None:
        self._periods = self.repository.list_periods()
        self._load_periods_table()
        active = self.repository.get_active_period()
        self._update_active_badge(active)
        if self._selected_period_id is not None:
            self._select_period_by_id(self._selected_period_id)
        elif self._periods:
            first_id = self._periods[0].id
            if first_id is not None:
                self._select_period_by_id(first_id)
        else:
            self._load_editor(None)

    def _update_active_badge(self, active: OperationalPeriodRecord | None) -> None:
        colors = _status_colors()
        if active is not None:
            _, bg, fg = colors["Active"]
            self._active_badge.setText(f"Active: OP {active.number}")
            self._active_badge.setStyleSheet(
                f"padding: 4px 10px; border-radius: 4px; font-weight: 600;"
                f"background: {bg}; color: {fg};"
            )
        else:
            self._active_badge.setText("No active period")
            dark = _is_dark_mode()
            self._active_badge.setStyleSheet(
                "padding: 4px 10px; border-radius: 4px; font-weight: 600;"
                + ("background: #3a2e00; color: #ffb300;" if dark else "background: #fff3cd; color: #856404;")
            )

    def _load_periods_table(self) -> None:
        colors = _status_colors()
        dark = _is_dark_mode()
        self.periods_table.setRowCount(len(self._periods))
        for row_idx, period in enumerate(self._periods):
            status = period.status or "Planned"
            row_bg, _, _ = colors.get(status, colors["Planned"])

            op_text = f"OP {period.number}"
            if status == "Active":
                op_text = "● " + op_text

            values = [
                op_text,
                status,
                _friendly_dt(period.start_time),
                _friendly_dt(period.end_time),
                _duration_label(period.start_time, period.end_time),
            ]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, period.id)
                item.setBackground(QColor(row_bg))
                if status == "Active":
                    item.setForeground(QColor(_ACTIVE_ROW_FG_DARK if dark else _ACTIVE_ROW_FG_LIGHT))
                elif status == "Complete":
                    item.setForeground(QColor(_COMPLETE_ROW_FG_DARK if dark else _COMPLETE_ROW_FG_LIGHT))
                self.periods_table.setItem(row_idx, col_idx, item)

    def _on_selection_changed(self) -> None:
        items = self.periods_table.selectedItems()
        if not items:
            return
        period_id = items[0].data(Qt.UserRole)
        if period_id is None:
            return
        new_id = int(period_id)
        if new_id == self._selected_period_id:
            return
        # switching rows — guard if dirty
        if self._dirty:
            if not self._guard_dirty():
                # re-select the old row without triggering this handler again
                self.periods_table.blockSignals(True)
                self._select_period_by_id(self._selected_period_id or new_id)
                self.periods_table.blockSignals(False)
                return
        self._selected_period_id = new_id
        self._load_editor(self.repository.get_period(self._selected_period_id))
        self._clear_dirty()

    def _select_period_by_id(self, period_id: int) -> None:
        for row in range(self.periods_table.rowCount()):
            item = self.periods_table.item(row, 0)
            if item and item.data(Qt.UserRole) == period_id:
                self.periods_table.selectRow(row)
                return

    def _load_editor(self, period: OperationalPeriodRecord | None) -> None:
        now = datetime.now().replace(second=0, microsecond=0)
        if period is None:
            self._selected_period_id = None
            self.number_spin.setValue(self.repository.next_number())
            self.name_edit.clear()
            self.status_combo.setCurrentText("Planned")
            self.start_edit.setDateTime(now)
            self.end_edit.setDateTime(now + timedelta(hours=12))
            self.objectives_edit.clear()
            self.weather_edit.clear()
            self.safety_edit.clear()
            for label in self.summary_labels.values():
                label.setText("0")
            self._set_active_btn.setEnabled(False)
            self._clear_dirty()
            return

        self.number_spin.setValue(period.number)
        self.name_edit.setText(period.name)
        self.status_combo.setCurrentText(period.status)
        self.start_edit.setDateTime(_parse_storage_dt(period.start_time))
        self.end_edit.setDateTime(_parse_storage_dt(period.end_time))
        self.objectives_edit.setPlainText(period.objectives)
        self.weather_edit.setPlainText(period.weather_summary)
        self.safety_edit.setPlainText(period.safety_message)
        summary = self.repository.period_summary(period.id or 0)
        for key, label in self.summary_labels.items():
            label.setText(str(summary.get(key, 0)))
        self._set_active_btn.setEnabled(period.status != "Active")
        self._clear_dirty()

    # ------------------------------------------------------------------
    # Payload helpers
    # ------------------------------------------------------------------

    def _payload(self) -> dict[str, str | int]:
        return {
            "number": self.number_spin.value(),
            "name": self.name_edit.text().strip(),
            "status": self.status_combo.currentText(),
            "start_time": _storage_dt(self.start_edit),
            "end_time": _storage_dt(self.end_edit),
            "objectives": self.objectives_edit.toPlainText().strip(),
            "weather_summary": self.weather_edit.toPlainText().strip(),
            "safety_message": self.safety_edit.toPlainText().strip(),
        }

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _new_period(self) -> None:
        if not self._guard_dirty():
            return
        self.periods_table.clearSelection()
        self._load_editor(None)

    def _save_selected(self) -> None:
        try:
            if self._selected_period_id is None:
                record = self.repository.create_period(self._payload())
            else:
                record = self.repository.update_period(self._selected_period_id, self._payload())
        except Exception as exc:
            QMessageBox.warning(self, "Operational Period", str(exc))
            return
        self._selected_period_id = record.id
        self._clear_dirty()
        self.refresh_all()

    def _clone_selected(self) -> None:
        if self._selected_period_id is None:
            QMessageBox.information(self, "Clone Period", "Select a period to clone first.")
            return
        if not self._guard_dirty():
            return
        try:
            record = self.repository.clone_period(self._selected_period_id)
        except Exception as exc:
            QMessageBox.warning(self, "Clone Period", str(exc))
            return
        self._selected_period_id = record.id
        self.refresh_all()

    def _set_active_selected(self) -> None:
        if self._selected_period_id is None:
            QMessageBox.information(self, "Active Period", "Select a period first.")
            return
        try:
            self.repository.set_active_period(self._selected_period_id)
        except Exception as exc:
            QMessageBox.warning(self, "Active Period", str(exc))
            return
        self.refresh_all()


def make_operational_period_manager_panel(
    incident_id: str | None = None,
    parent: QWidget | None = None,
) -> OperationalPeriodManagerPanel:
    return OperationalPeriodManagerPanel(incident_id=incident_id, parent=parent)


__all__ = ["OperationalPeriodManagerPanel", "make_operational_period_manager_panel"]
