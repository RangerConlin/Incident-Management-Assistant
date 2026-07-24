from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .repository import OperationalPeriodRecord, OperationalPeriodRepository
from utils.styles import get_palette, subscribe_theme, task_status_colors


_STATUS_COLOR_KEYS = {
    "Active": "complete",
    "Planned": "planned",
    "Complete": "complete",
    "Canceled": "cancelled",
}


def _color_name(key: str, fallback: str = "ctrl_border") -> str:
    pal = get_palette()
    color = pal.get(key) or pal.get(fallback)
    return color.name() if color is not None else ""


def _status_brushes(status: str):
    key = _STATUS_COLOR_KEYS.get(status)
    if key:
        return task_status_colors().get(key)
    return None


def _brush_color(brushes, role: str, fallback: str) -> str:
    if brushes and role in brushes:
        return brushes[role].color().name()
    return _color_name(fallback)


def _chip(text: str, brushes, parent: QWidget | None = None) -> QLabel:
    label = QLabel(text, parent)
    label.setAlignment(Qt.AlignCenter)
    label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    label.setStyleSheet(
        f"background:{_brush_color(brushes, 'bg', 'ctrl_bg')}; "
        f"color:{_brush_color(brushes, 'fg', 'fg')}; "
        f"border:1px solid {_color_name('ctrl_border')}; "
        "padding:2px 8px; border-radius:4px; font-weight:700;"
    )
    return label


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


class _OperationalPeriodCard(QFrame):
    selected = Signal(int)

    def __init__(
        self,
        period: OperationalPeriodRecord,
        *,
        selected: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._period = period
        self._selected = selected
        self.setFrameShape(QFrame.StyledPanel)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        period = self._period
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(7)

        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel(f"OP {period.number}  {period.display_name}", self)
        title.setWordWrap(True)
        title.setStyleSheet("font-weight:700; font-size:14px; background:transparent;")
        title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        header.addWidget(title, 1)
        header.addWidget(_chip(period.status or "Planned", _status_brushes(period.status), self))
        layout.addLayout(header)

        times = QHBoxLayout()
        times.setSpacing(16)
        times.addWidget(self._muted_label(f"Start  {_friendly_dt(period.start_time)}"))
        times.addWidget(self._muted_label(f"End  {_friendly_dt(period.end_time)}"))
        times.addWidget(self._muted_label(f"Duration  {_duration_label(period.start_time, period.end_time)}"))
        times.addStretch(1)
        layout.addLayout(times)

        notes = []
        if period.objectives:
            notes.append(("Objectives", period.objectives))
        if period.weather_summary:
            notes.append(("Weather", period.weather_summary))
        if period.safety_message:
            notes.append(("Safety", period.safety_message))
        if notes:
            note_text = "   ".join(f"{label}: {self._clip_text(text)}" for label, text in notes[:2])
            note_label = QLabel(note_text, self)
            note_label.setWordWrap(True)
            note_label.setStyleSheet(f"color:{_color_name('muted')}; background:transparent;")
            layout.addWidget(note_label)

        if period.updated_at:
            updated = self._muted_label(f"Updated {_friendly_dt(period.updated_at)}")
            updated.setStyleSheet(updated.styleSheet() + " font-size:11px;")
            layout.addWidget(updated)

    def _apply_style(self) -> None:
        status = self._period.status or "Planned"
        brushes = _status_brushes(status)
        border = _color_name("ctrl_focus" if self._selected else "ctrl_border")
        left_border = _brush_color(brushes, "bg", "ctrl_border")
        background = _color_name("ctrl_hover" if self._selected else "bg_raised")
        self.setStyleSheet(
            "_OperationalPeriodCard { "
            f"background-color:{background}; "
            f"border:1px solid {border}; "
            f"border-left:4px solid {left_border}; "
            "border-radius:8px; "
            "}"
        )

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton and self._period.id is not None:
            self.selected.emit(int(self._period.id))
        super().mousePressEvent(event)

    @staticmethod
    def _clip_text(text: str, limit: int = 90) -> str:
        compact = " ".join(text.split())
        if len(compact) <= limit:
            return compact
        return compact[: limit - 3].rstrip() + "..."

    @staticmethod
    def _muted_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"color:{_color_name('muted')}; background:transparent;")
        label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        return label


class OperationalPeriodManagerPanel(QWidget):
    def __init__(self, incident_id: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.repository = OperationalPeriodRepository(incident_id=incident_id)
        self._periods: list[OperationalPeriodRecord] = []
        self._active_period: OperationalPeriodRecord | None = None
        self._selected_period_id: int | None = None
        self._dirty = False
        self._loading_editor = False
        self._autosaving = False
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(900)
        self._autosave_timer.timeout.connect(self._autosave_selected)
        self.setObjectName("OperationalPeriodManagerPanel")
        self.setWindowTitle("Planning - Operational Period Manager")
        self.resize(1000, 600)
        self._build_ui()
        subscribe_theme(self, self._on_theme_changed)
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

        board = QWidget(self)
        board_layout = QVBoxLayout(board)
        board_layout.setContentsMargins(0, 0, 0, 0)
        board_layout.setSpacing(8)
        root.addWidget(board, 1)

        self.periods_scroll = QScrollArea(board)
        self.periods_scroll.setWidgetResizable(True)
        self.periods_scroll.setFrameShape(QFrame.NoFrame)
        self.periods_card_container = QWidget(self.periods_scroll)
        self.periods_card_layout = QVBoxLayout(self.periods_card_container)
        self.periods_card_layout.setContentsMargins(0, 0, 0, 0)
        self.periods_card_layout.setSpacing(8)
        self.periods_card_layout.addStretch(1)
        self.periods_scroll.setWidget(self.periods_card_container)
        board_layout.addWidget(self.periods_scroll, 1)

        self._drawer_open = False
        self._drawer = QFrame(self.periods_card_container)
        self._drawer.setObjectName("OperationalPeriodDrawer")
        self._drawer.setFrameShape(QFrame.StyledPanel)
        self._drawer.setAttribute(Qt.WA_StyledBackground, True)
        drawer_layout = QVBoxLayout(self._drawer)
        drawer_layout.setContentsMargins(10, 10, 10, 10)
        drawer_layout.setSpacing(10)

        drawer_header = QHBoxLayout()
        self._drawer_title = QLabel("Period Details", self._drawer)
        self._drawer_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        close_btn = QPushButton("Close", self._drawer)
        close_btn.clicked.connect(self._close_drawer)
        drawer_header.addWidget(self._drawer_title, 1)
        drawer_header.addWidget(close_btn)
        drawer_layout.addLayout(drawer_header)

        drawer_scroll = QScrollArea(self._drawer)
        drawer_scroll.setWidgetResizable(True)
        drawer_scroll.setFrameShape(QFrame.NoFrame)
        drawer_content = QWidget(drawer_scroll)
        drawer_content_layout = QVBoxLayout(drawer_content)
        drawer_content_layout.setContentsMargins(0, 0, 0, 0)
        drawer_content_layout.setSpacing(10)
        drawer_scroll.setWidget(drawer_content)
        drawer_layout.addWidget(drawer_scroll, 1)

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
        drawer_content_layout.addWidget(basics_group)

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
        drawer_content_layout.addWidget(summary_group)

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
        drawer_content_layout.addWidget(notes_group)
        drawer_content_layout.addStretch(1)

        actions = QHBoxLayout()
        actions.addStretch()
        self._set_active_btn = QPushButton("Set as Active Period")
        self._set_active_btn.clicked.connect(self._set_active_selected)
        self._save_btn = QPushButton("Saved")
        self._save_btn.setDefault(True)
        self._save_btn.clicked.connect(self._save_selected)
        actions.addWidget(self._set_active_btn)
        actions.addWidget(self._save_btn)
        drawer_layout.addLayout(actions)

        self._drawer.hide()
        self._apply_drawer_style()

    # ------------------------------------------------------------------
    # Dirty tracking
    # ------------------------------------------------------------------

    def _mark_dirty(self, *_) -> None:
        if self._loading_editor or self._autosaving:
            return
        if not self._dirty:
            self._dirty = True
            self._save_btn.setText("Saving...")
        self._autosave_timer.start()

    def _apply_duration(self, hours: int) -> None:
        new_end = self.start_edit.dateTime().addSecs(hours * 3600)
        self.end_edit.setDateTime(new_end)

    def _clear_dirty(self) -> None:
        self._dirty = False
        self._autosave_timer.stop()
        self._save_btn.setText("Saved")

    def _guard_dirty(self) -> bool:
        """Return True (safe to proceed) or False (user cancelled)."""
        if not self._dirty:
            return True
        return self._autosave_selected()

    def _open_drawer(self) -> None:
        self._drawer_open = True
        self._drawer.show()
        self._render_period_cards()

    def _close_drawer(self) -> None:
        if not self._guard_dirty():
            return
        self._drawer_open = False
        self._selected_period_id = None
        self._load_editor(None)
        self._clear_dirty()
        self._drawer.hide()
        self._render_period_cards()

    def _collapse_selected_drawer(self) -> None:
        if not self._guard_dirty():
            return
        self._drawer_open = False
        self._drawer.hide()
        self._render_period_cards()

    def _apply_drawer_style(self) -> None:
        self._drawer.setStyleSheet(
            "QFrame#OperationalPeriodDrawer { "
            f"background-color:{_color_name('bg_raised')}; "
            f"border:1px solid {_color_name('ctrl_border')}; "
            "border-radius:8px; "
            "}"
        )

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def refresh_all(self) -> None:
        self._periods = self.repository.list_periods()
        self._render_period_cards()
        self._active_period = self.repository.get_active_period()
        self._update_active_badge(self._active_period)
        if self._selected_period_id is not None:
            self._select_period_by_id(self._selected_period_id)
        else:
            self._load_editor(None)

    def _on_theme_changed(self, _name: str) -> None:
        self._render_period_cards()
        self._update_active_badge(self._active_period)
        self._apply_drawer_style()

    def _update_active_badge(self, active: OperationalPeriodRecord | None) -> None:
        if active is not None:
            brushes = _status_brushes("Active")
            self._active_badge.setText(f"Active: OP {active.number}")
            self._active_badge.setStyleSheet(
                "padding: 4px 10px; border-radius: 4px; font-weight: 600;"
                f"background:{_brush_color(brushes, 'bg', 'ctrl_bg')}; "
                f"color:{_brush_color(brushes, 'fg', 'fg')};"
            )
        else:
            self._active_badge.setText("No active period")
            self._active_badge.setStyleSheet(
                "padding: 4px 10px; border-radius: 4px; font-weight: 600;"
                f"background:{_color_name('ctrl_bg')}; color:{_color_name('warning')};"
            )

    def _render_period_cards(self) -> None:
        self._detach_drawer()
        while self.periods_card_layout.count() > 1:
            item = self.periods_card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._periods:
            empty = QLabel("No operational periods defined.", self.periods_card_container)
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color:{_color_name('muted')}; font-style:italic; padding:24px;")
            self.periods_card_layout.insertWidget(0, empty)
            return

        for period in self._periods:
            card = _OperationalPeriodCard(
                period,
                selected=period.id == self._selected_period_id,
                parent=self.periods_card_container,
            )
            card.selected.connect(self._request_select_period)
            self.periods_card_layout.insertWidget(self.periods_card_layout.count() - 1, card)
            if self._drawer_open and period.id == self._selected_period_id:
                self.periods_card_layout.insertWidget(self.periods_card_layout.count() - 1, self._drawer)

        if self._drawer_open and self._selected_period_id is None:
            self.periods_card_layout.insertWidget(0, self._drawer)

    def _detach_drawer(self) -> None:
        for index in range(self.periods_card_layout.count()):
            item = self.periods_card_layout.itemAt(index)
            if item and item.widget() is self._drawer:
                self.periods_card_layout.takeAt(index)
                return

    def _request_select_period(self, new_id: int) -> None:
        if new_id == self._selected_period_id:
            if self._drawer_open:
                self._collapse_selected_drawer()
            else:
                self._open_drawer()
            return
        if self._dirty:
            if not self._guard_dirty():
                self._render_period_cards()
                return
        self._selected_period_id = new_id
        self._load_editor(self.repository.get_period(self._selected_period_id))
        self._clear_dirty()
        self._open_drawer()

    def _select_period_by_id(self, period_id: int) -> None:
        if any(period.id == period_id for period in self._periods):
            self._selected_period_id = period_id
            self._load_editor(self.repository.get_period(period_id))
            self._clear_dirty()
            self._open_drawer()
            return

    def _load_editor(self, period: OperationalPeriodRecord | None) -> None:
        self._loading_editor = True
        now = datetime.now().replace(second=0, microsecond=0)
        try:
            if period is None:
                self._selected_period_id = None
                self._drawer_title.setText("New Period")
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

            self._drawer_title.setText(f"OP {period.number} Details")
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
        finally:
            self._loading_editor = False

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

    def _autosave_selected(self) -> bool:
        if self._loading_editor or self._autosaving:
            return True
        if not self._dirty:
            return True
        payload = self._payload()
        try:
            self.repository.validate_no_overlap(
                str(payload["start_time"]),
                str(payload["end_time"]),
                exclude_id=self._selected_period_id,
            )
        except ValueError as exc:
            self._save_btn.setText("Fix Dates")
            self._save_btn.setToolTip(str(exc))
            return False

        self._autosave_timer.stop()
        self._autosaving = True
        self._save_btn.setText("Saving...")
        self._save_btn.setToolTip("")
        try:
            if self._selected_period_id is None:
                record = self.repository.create_period(payload)
            else:
                record = self.repository.update_period(self._selected_period_id, payload)
        except Exception as exc:
            self._save_btn.setText("Save Failed")
            self._save_btn.setToolTip(str(exc))
            return False
        finally:
            self._autosaving = False

        self._selected_period_id = record.id
        self._replace_period(record)
        if record.status == "Active":
            self._active_period = record
            self._update_active_badge(record)
        elif self._active_period is not None and self._active_period.id == record.id:
            self._active_period = None
            self._update_active_badge(None)
        self._set_active_btn.setEnabled(record.status != "Active")
        self._clear_dirty()
        self._drawer_title.setText(f"OP {record.number} Details")
        self._render_period_cards()
        return True

    def _replace_period(self, record: OperationalPeriodRecord) -> None:
        if record.id is None:
            return
        for idx, existing in enumerate(self._periods):
            if existing.id == record.id:
                self._periods[idx] = record
                break
        else:
            self._periods.append(record)
        self._periods.sort(key=lambda period: period.number)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _new_period(self) -> None:
        if not self._guard_dirty():
            return
        self._selected_period_id = None
        self._render_period_cards()
        self._load_editor(None)
        self._open_drawer()

    def _save_selected(self) -> None:
        if not self._dirty:
            return
        self._autosave_selected()

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
