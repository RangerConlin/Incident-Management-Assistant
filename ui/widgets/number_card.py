"""NumberCardWidget — Universal configurable metric card.

A dockable/dashboard widget that displays a live count from IncidentCache,
with customizable colors, threshold-based logic, trend tracking, and
progress toward a target.

No QTimer polling — all updates arrive via IncidentCache push events.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QBrush, QPen
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.number_card_metrics import (
    NumberCardMetric,
    ThresholdRule,
    get_metric,
    list_metrics,
)

logger = logging.getLogger(__name__)

try:
    from utils.incident_cache import incident_cache
    HAS_CACHE = True
except Exception:
    incident_cache = None  # type: ignore[assignment]
    HAS_CACHE = False


# ── Configuration ────────────────────────────────────────────────────────────

@dataclass
class NumberCardConfig:
    """Per-instance configuration for a NumberCardWidget.

    Serialized to/from dict for persistence in LayoutTemplate metadata.
    """
    metric_id: str
    custom_label: str = ""
    fill_color: str = ""
    border_color: str = ""
    text_color: str = ""
    # Override thresholds (if empty, defaults from NumberCardMetric are used)
    thresholds: List[ThresholdRule] = field(default_factory=list)
    # Logic
    show_trend: bool = True
    target_value: int = 0
    # Display sizing
    size_w: int = 3
    size_h: int = 1

    @classmethod
    def from_metric(cls, metric: NumberCardMetric) -> "NumberCardConfig":
        return cls(
            metric_id=metric.id,
            custom_label=metric.label,
            fill_color=metric.default_fill,
            border_color=metric.default_color,
            text_color=metric.default_color,
            target_value=metric.target_value,
        )

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["thresholds"] = [
            {"operator": t.operator, "value": t.value,
             "fill_color": t.fill_color, "border_color": t.border_color,
             "text_color": t.text_color, "label": t.label}
            for t in self.thresholds
        ]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NumberCardConfig":
        raw = dict(data)
        thresholds_raw = raw.pop("thresholds", []) or []
        config = cls(**raw)
        config.thresholds = [
            ThresholdRule(**t) for t in thresholds_raw
        ]
        return config
# ── Number Card Widget ────────────────────────────────────────────────────────

class NumberCardWidget(QFrame):
    """Universal metric card showing a live count from IncidentCache.

    Layout::

        ┌──────────────────────────────────────┐
        │ PENDING TASKS               [⚙]  │  ← title + config button
        │                                      │
        │               12                     │  ← big number, centered
        │                                      │
        │    ▲ 3 from last check   ██░░ 8/10   │  ← trend / progress
        └──────────────────────────────────────┘
    """

    clicked = Signal()
    """Emitted when the card body (not config button) is clicked."""
    configChanged = Signal(object)
    """Emitted when configuration is updated; arg is the NumberCardConfig."""

    def __init__(
        self,
        config: NumberCardConfig | None = None,
        metric: NumberCardMetric | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("NumberCardWidget")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(140, 90)

        # Resolve config
        if config is None and metric is not None:
            config = NumberCardConfig.from_metric(metric)
        self._config: NumberCardConfig = config or NumberCardConfig(
            metric_id="tasks_pending",
            custom_label="Metric",
            fill_color="#1a1a1a",
            border_color="#888888",
            text_color="#888888",
        )
        self._metric: Optional[NumberCardMetric] = get_metric(self._config.metric_id) or metric

        # Trend tracking
        self._previous_value: Optional[int] = None
        self._current_value: int = 0

        # Build UI
        self._build_ui()

        # Subscribe to IncidentCache
        if HAS_CACHE and self._metric:
            col = self._metric.collection
            try:
                incident_cache.changed.connect(self._on_cache_changed)
                incident_cache.snapshotLoaded.connect(self._on_snapshot_loaded)
            except Exception:
                pass
            self._fetch_and_update()
        else:
            self._update_display(0)

    # ── UI construction ─────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 8, 14, 12)
        self._layout.setSpacing(2)

        # ── Title row ──────────────────────────────────────────────────────
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(4)

        self._title_label = QLabel(self._resolve_label())
        self._title_label.setObjectName("NumberCardTitle")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(9)
        self._title_label.setFont(title_font)
        self._title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        title_row.addWidget(self._title_label)

        # Config button (gear)
        self._config_button = QPushButton("⚙", self)
        self._config_button.setFixedSize(20, 20)
        self._config_button.setFlat(True)
        self._config_button.setToolTip("Configure this card")
        self._config_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._config_button.clicked.connect(self._open_config_dialog)
        title_row.addWidget(self._config_button)

        self._layout.addLayout(title_row)

        # ── Big number ─────────────────────────────────────────────────────
        self._value_label = QLabel("—")
        self._value_label.setObjectName("NumberCardValue")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val_font = QFont()
        val_font.setPointSize(32)
        val_font.setBold(True)
        self._value_label.setFont(val_font)
        self._value_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._layout.addWidget(self._value_label, 1)

        # ── Logic row (trend / progress) ───────────────────────────────────
        self._logic_row = QHBoxLayout()
        self._logic_row.setContentsMargins(0, 2, 0, 0)
        self._logic_row.setSpacing(8)

        self._trend_label = QLabel()
        self._trend_label.setObjectName("NumberCardTrend")
        trend_font = QFont()
        trend_font.setPointSize(10)
        self._trend_label.setFont(trend_font)

        self._progress_bar = _MiniProgressBar(self)
        self._progress_bar.setFixedHeight(4)

        self._logic_row.addWidget(self._trend_label)
        self._logic_row.addWidget(self._progress_bar, 1)
        self._layout.addLayout(self._logic_row)

        # ── Style ──────────────────────────────────────────────────────────
        self._apply_colors()

        # ── Mouse interaction ──────────────────────────────────────────────
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        child = self.childAt(event.position().toPoint())
        if child is not self._config_button:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        menu.addAction("Configure...", self._open_config_dialog)
        if self._metric and self._metric.view_action:
            menu.addAction(f"View {self._metric.label}", self.clicked.emit)
        menu.exec(event.globalPos())

    # ── Color / style ───────────────────────────────────────────────────────

    def _resolve_color(self, field: str) -> str:
        config_val = getattr(self._config, field, "")
        if config_val:
            return config_val
        if self._metric:
            key = f"default_{field.replace('_color', '')}"
            return getattr(self._metric, key, "#888888")
        return "#888888"

    def _resolve_label(self) -> str:
        if self._config.custom_label:
            return self._config.custom_label
        return self._metric.label if self._metric else "Metric"

    def _apply_colors(self) -> None:
        text_color = self._resolve_color("text_color")
        fill_color = self._resolve_color("fill_color")
        border_color = self._resolve_color("border_color")

        rules = self._config.thresholds or (
            self._metric.default_thresholds if self._metric else []
        )
        for rule in rules:
            if rule.evaluate(self._current_value):
                text_color = rule.text_color or text_color
                fill_color = rule.fill_color or fill_color
                border_color = rule.border_color or border_color
                break

        self.setStyleSheet(f"""
            QFrame#NumberCardWidget {{
                background-color: {fill_color};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
            QFrame#NumberCardWidget QLabel#NumberCardTitle {{
                color: {border_color};
                font-size: 10px;
                letter-spacing: 0.5px;
            }}
            QFrame#NumberCardWidget QLabel#NumberCardValue {{
                color: {text_color};
            }}
            QFrame#NumberCardWidget QLabel#NumberCardTrend {{
                color: {text_color};
            }}
        """)
# ── Data methods ────────────────────────────────────────────────────────

    def _on_cache_changed(self, collection: str, op: str, doc_id: str) -> None:
        if self._metric and collection == self._metric.collection:
            self._fetch_and_update()

    def _on_snapshot_loaded(self) -> None:
        if self._config.metric_id:
            self._metric = get_metric(self._config.metric_id)
        self._fetch_and_update()

    def _fetch_and_update(self) -> None:
        if not HAS_CACHE or not self._metric or incident_cache is None:
            return
        try:
            docs = incident_cache.get_all(self._metric.collection)
            value = self._metric.value_fn(docs)
        except Exception:
            logger.exception("Failed to query cache for '%s'",
                             self._metric.collection)
            return
        self._update_display(value)

    def _update_display(self, value: int) -> None:
        self._current_value = value
        self._value_label.setText(str(value))
        self._title_label.setText(self._resolve_label().upper())

        # Trend indicator
        if self._config.show_trend and self._previous_value is not None:
            delta = value - self._previous_value
            if delta > 0:
                self._trend_label.setText(f"▲ {delta}")
            elif delta < 0:
                self._trend_label.setText(f"▼ {abs(delta)}")
            else:
                self._trend_label.setText("—")
            self._trend_label.setVisible(True)
        else:
            self._trend_label.setVisible(False)

        # Progress bar
        target = self._config.target_value or (
            self._metric.target_value if self._metric else 0
        )
        if target > 0:
            pct = min(100, int(value * 100 / target))
            self._progress_bar.set_progress(pct)
            self._progress_bar.setVisible(True)
        else:
            self._progress_bar.setVisible(False)

        self._previous_value = value
        self._apply_colors()

    # ── Configuration ──────────────────────────────────────────────────────

    def _open_config_dialog(self) -> None:
        dialog = NumberCardConfigDialog(self._config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._config = dialog.get_config()
            self._metric = get_metric(self._config.metric_id)
            self._previous_value = None
            self._apply_colors()
            self._fetch_and_update()
            self.configChanged.emit(self._config)

    def get_config(self) -> NumberCardConfig:
        return self._config
# ── Mini Progress Bar ────────────────────────────────────────────────────────

class _MiniProgressBar(QWidget):
    """Thin horizontal progress bar used in the logic row."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._percent: int = 0
        self.setFixedHeight(4)
        self.setMinimumWidth(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def set_progress(self, percent: int) -> None:
        self._percent = max(0, min(100, percent))
        self.update()

    def paintEvent(self, event) -> None:
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background track
        painter.setBrush(QBrush(QColor("#333333")))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.drawRoundedRect(0, 0, w, h, 2, 2)

        # Filled portion
        fill_w = max(4, int(w * self._percent / 100))
        if self._percent < 30:
            bar_color = QColor("#f44336")
        elif self._percent < 70:
            bar_color = QColor("#ff9800")
        else:
            bar_color = QColor("#4caf50")
        painter.setBrush(QBrush(bar_color))
        painter.drawRoundedRect(0, 0, fill_w, h, 2, 2)
        painter.end()


class _ToggleCheckbox(QWidget):
    """A simple clickable toggle row for the config dialog."""

    def __init__(self, label: str, checked: bool = False, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        from PySide6.QtWidgets import QCheckBox
        self._cb = QCheckBox(label, self)
        self._cb.setChecked(checked)
        layout.addWidget(self._cb)
        layout.addStretch()

    def isChecked(self) -> bool:
        return self._cb.isChecked()
# ── Configuration Dialog ────────────────────────────────────────────────────

class NumberCardConfigDialog(QDialog):
    """Dialog for configuring a NumberCardWidget's metric, colors, and logic."""

    def __init__(
        self,
        config: NumberCardConfig,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configure Metric Card")
        self.setMinimumWidth(420)
        self._config = config
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QFormLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)

        # Metric selector
        self._metric_combo = QComboBox(self)
        self._metrics = list_metrics()
        for idx, m in enumerate(self._metrics):
            self._metric_combo.addItem(m.label, m.id)
            if m.id == self._config.metric_id:
                self._metric_combo.setCurrentIndex(idx)
        self._metric_combo.currentIndexChanged.connect(self._on_metric_changed)
        layout.addRow("Metric:", self._metric_combo)

        # Custom label
        self._label_edit = QLineEdit(self._config.custom_label or "", self)
        self._label_edit.setPlaceholderText("Leave blank to use metric name")
        layout.addRow("Custom Label:", self._label_edit)

        # Colors
        self._fill_btn = self._color_button("Fill", self._config.fill_color)
        layout.addRow("Fill Color:", self._fill_btn)

        self._border_btn = self._color_button("Border", self._config.border_color)
        layout.addRow("Border Color:", self._border_btn)

        self._text_btn = self._color_button("Text", self._config.text_color)
        layout.addRow("Text Color:", self._text_btn)

        # Logic
        self._show_trend_cb = _ToggleCheckbox("Show trend ▲/▼", self._config.show_trend)
        layout.addRow("", self._show_trend_cb)

        self._target_spin = QSpinBox(self)
        self._target_spin.setRange(0, 999999)
        self._target_spin.setValue(self._config.target_value)
        self._target_spin.setToolTip("Set > 0 to show a progress bar toward this target")
        layout.addRow("Target Value:", self._target_spin)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
    def _color_button(self, label: str, initial: str) -> QPushButton:
        btn = QPushButton(self)
        btn.setFixedSize(60, 24)
        self._update_swatch(btn, initial or "#666666")
        btn.clicked.connect(lambda: self._pick_color(btn, label))
        return btn

    def _update_swatch(self, btn: QPushButton, color: str) -> None:
        try:
            QColor(color)
            btn.setStyleSheet(
                f"background-color: {color}; border: 1px solid #555; border-radius: 3px;"
            )
        except Exception:
            pass

    def _pick_color(self, btn: QPushButton, label: str) -> None:
        current = btn.property("_color") or "#888888"
        try:
            color = QColor(current)
        except Exception:
            color = QColor("#888888")
        chosen = QColorDialog.getColor(color, self, f"Choose {label} Color")
        if chosen.isValid():
            self._update_swatch(btn, chosen.name())

    def _on_metric_changed(self) -> None:
        metric_id = self._metric_combo.currentData()
        metric = get_metric(str(metric_id)) if metric_id else None
        if metric:
            if not self._label_edit.text():
                self._label_edit.setPlaceholderText(metric.label)
            if not self._config.fill_color:
                self._update_swatch(self._fill_btn, metric.default_fill)
            if not self._config.border_color:
                self._update_swatch(self._border_btn, metric.default_color)
            if not self._config.text_color:
                self._update_swatch(self._text_btn, metric.default_color)

    def get_config(self) -> NumberCardConfig:
        metric_id = self._metric_combo.currentData() or self._config.metric_id
        return NumberCardConfig(
            metric_id=str(metric_id),
            custom_label=self._label_edit.text().strip(),
            fill_color=self._extract_color(self._fill_btn),
            border_color=self._extract_color(self._border_btn),
            text_color=self._extract_color(self._text_btn),
            show_trend=bool(self._show_trend_cb.isChecked()),
            target_value=self._target_spin.value(),
        )

    def _extract_color(self, btn: QPushButton) -> str:
        ss = btn.styleSheet()
        if "background-color:" in ss:
            try:
                return ss.split("background-color:")[1].split(";")[0].strip()
            except Exception:
                pass
        return ""