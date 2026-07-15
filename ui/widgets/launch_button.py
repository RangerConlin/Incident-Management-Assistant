"""LaunchButtonWidget — a dockable button that opens a chosen application
screen when clicked.

Routes through ``MainWindow.open_module`` the same way
``IncidentDashboardPanel`` does for its quick-action buttons, so it works
with any menu-registered ``module_key`` without importing ``main`` directly.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.module_actions import MODULE_ACTIONS, list_module_actions

logger = logging.getLogger(__name__)


@dataclass
class LaunchButtonConfig:
    """Per-instance configuration for a LaunchButtonWidget."""

    module_key: str = "window.home_dashboard"
    label: str = ""
    fill_color: str = "#2d6cdf"
    text_color: str = "#ffffff"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LaunchButtonConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class LaunchButtonWidget(QFrame):
    """A big configurable button that opens a specific screen when clicked."""

    configChanged = Signal(object)

    def __init__(
        self,
        config: LaunchButtonConfig | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("LaunchButtonWidget")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(140, 60)
        self._config = config or LaunchButtonConfig()
        self._build_ui()
        self._apply_style()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 6, 6)
        layout.setSpacing(4)

        self._label_btn = QPushButton(self._resolve_label(), self)
        self._label_btn.setFlat(True)
        self._label_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        self._label_btn.setFont(font)
        self._label_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._label_btn.clicked.connect(self._launch)
        layout.addWidget(self._label_btn, 1)

        self._config_button = QPushButton("⚙", self)
        self._config_button.setFixedSize(20, 20)
        self._config_button.setFlat(True)
        self._config_button.setToolTip("Configure this button")
        self._config_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._config_button.clicked.connect(self._open_config_dialog)
        layout.addWidget(self._config_button)

    def _resolve_label(self) -> str:
        if self._config.label:
            return self._config.label
        return MODULE_ACTIONS.get(self._config.module_key, self._config.module_key)

    def _apply_style(self) -> None:
        fill = self._config.fill_color or "#2d6cdf"
        text = self._config.text_color or "#ffffff"
        self.setStyleSheet(f"""
            QFrame#LaunchButtonWidget {{
                background-color: {fill};
                border: 1px solid {fill};
                border-radius: 8px;
            }}
            QFrame#LaunchButtonWidget QPushButton {{
                color: {text};
                border: none;
                background: transparent;
            }}
        """)

    # ------------------------------------------------------------------
    def _launch(self) -> None:
        window = self.window()
        opener = getattr(window, "open_module", None)
        if not callable(opener):
            logger.info("LaunchButtonWidget: no open_module handler available on %r", window)
            return
        try:
            opener(self._config.module_key)
        except Exception:
            logger.exception("LaunchButtonWidget: failed to open module %s", self._config.module_key)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        child = self.childAt(event.position().toPoint())
        if child is None or child is self:
            self._launch()
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    def _open_config_dialog(self) -> None:
        dialog = LaunchButtonConfigDialog(self._config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._config = dialog.get_config()
            self._label_btn.setText(self._resolve_label())
            self._apply_style()
            self.configChanged.emit(self._config)

    def get_config(self) -> LaunchButtonConfig:
        return self._config


class LaunchButtonConfigDialog(QDialog):
    """Dialog for picking the destination screen and label/colors."""

    def __init__(self, config: LaunchButtonConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configure Launch Button")
        self.setMinimumWidth(380)
        self._config = config
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QFormLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)

        self._target_combo = QComboBox(self)
        for idx, (key, label) in enumerate(list_module_actions()):
            self._target_combo.addItem(label, key)
            if key == self._config.module_key:
                self._target_combo.setCurrentIndex(idx)
        layout.addRow("Opens:", self._target_combo)

        self._label_edit = QLineEdit(self._config.label or "", self)
        self._label_edit.setPlaceholderText("Leave blank to use the screen's name")
        layout.addRow("Button Label:", self._label_edit)

        self._fill_btn = self._color_button(self._config.fill_color)
        layout.addRow("Fill Color:", self._fill_btn)

        self._text_btn = self._color_button(self._config.text_color)
        layout.addRow("Text Color:", self._text_btn)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _color_button(self, initial: str) -> QPushButton:
        btn = QPushButton(self)
        btn.setFixedSize(60, 24)
        self._update_swatch(btn, initial or "#666666")
        btn.clicked.connect(lambda: self._pick_color(btn))
        return btn

    @staticmethod
    def _update_swatch(btn: QPushButton, color: str) -> None:
        try:
            QColor(color)
            btn.setStyleSheet(f"background-color: {color}; border: 1px solid #555; border-radius: 3px;")
        except Exception:
            pass

    def _pick_color(self, btn: QPushButton) -> None:
        from PySide6.QtWidgets import QColorDialog

        current = self._extract_color(btn) or "#888888"
        try:
            color = QColor(current)
        except Exception:
            color = QColor("#888888")
        chosen = QColorDialog.getColor(color, self, "Choose Color")
        if chosen.isValid():
            self._update_swatch(btn, chosen.name())

    @staticmethod
    def _extract_color(btn: QPushButton) -> str:
        ss = btn.styleSheet()
        if "background-color:" in ss:
            try:
                return ss.split("background-color:")[1].split(";")[0].strip()
            except Exception:
                pass
        return ""

    def get_config(self) -> LaunchButtonConfig:
        module_key = self._target_combo.currentData() or self._config.module_key
        return LaunchButtonConfig(
            module_key=str(module_key),
            label=self._label_edit.text().strip(),
            fill_color=self._extract_color(self._fill_btn) or "#2d6cdf",
            text_color=self._extract_color(self._text_btn) or "#ffffff",
        )
