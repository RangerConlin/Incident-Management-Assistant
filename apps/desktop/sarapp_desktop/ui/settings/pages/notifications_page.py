"""Notifications settings page."""

from __future__ import annotations

import os
import sys
import subprocess

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..binding import bind_checkbox, bind_slider

_CATEGORY_LABELS = {
    "operations":     "Operations",
    "communications": "Communications",
    "safety":         "Safety",
    "logistics":      "Logistics",
    "planning":       "Planning",
    "administrative": "Administrative",
    "system":         "System",
}
_SEVERITY_LABELS = {
    "informational": "Informational",
    "routine":       "Routine",
    "priority":      "Priority",
    "emergency":     "Emergency",
}
_NO_SOUND = "(none)"


class NotificationsPage(QWidget):
    """Alerting and notification preferences."""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self._bridge = bridge
        self._combos: dict[tuple[str, str], QComboBox] = {}

        # Outer scroll so the page doesn't overflow with 16 rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.NoFrame)

        inner = QWidget()
        root = QVBoxLayout(inner)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        # ── General ──────────────────────────────────────────────────
        general_group = QGroupBox("General")
        general_form = QFormLayout(general_group)
        general_form.setSpacing(10)

        sound_alerts = QCheckBox("Enable Sound Alerts")
        bind_checkbox(sound_alerts, bridge, "soundAlerts", True)
        general_form.addRow(sound_alerts)

        self._volume_slider = QSlider(Qt.Horizontal)
        self._volume_slider.setRange(0, 100)
        bind_slider(self._volume_slider, bridge, "volume", 75)
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        general_form.addRow("Volume:", self._volume_slider)

        critical_override = QCheckBox("Critical Alerts Override Mute")
        bind_checkbox(critical_override, bridge, "criticalOverride", True)
        general_form.addRow(critical_override)

        notify_tasks = QCheckBox("Notify on Task Updates")
        bind_checkbox(notify_tasks, bridge, "notifyOnTasks", True)
        general_form.addRow(notify_tasks)

        root.addWidget(general_group)

        # ── Per-category/severity sound groups ────────────────────────
        from notifications.services.sound_player import CATEGORIES, SEVERITIES
        from notifications.models.notification import CATEGORY_TOAST_THRESHOLDS

        for cat in CATEGORIES:
            group = QGroupBox(_CATEGORY_LABELS[cat])
            form = QFormLayout(group)
            form.setSpacing(8)

            # Toast threshold selector
            threshold_combo = QComboBox()
            for sev in SEVERITIES:
                threshold_combo.addItem(_SEVERITY_LABELS[sev], sev)
            saved_threshold = self._get(f"notification.threshold.{cat}") or CATEGORY_TOAST_THRESHOLDS.get(cat, "routine")
            idx = next((i for i in range(threshold_combo.count()) if threshold_combo.itemData(i) == saved_threshold), 0)
            threshold_combo.setCurrentIndex(idx)
            threshold_combo.currentIndexChanged.connect(
                lambda _, c=cat, cb=threshold_combo: self._on_threshold_changed(c, cb.currentData())
            )
            form.addRow("Show toasts for:", threshold_combo)
            form.addRow(self._make_separator())

            for sev in SEVERITIES:
                row = QHBoxLayout()
                row.setSpacing(6)

                combo = QComboBox()
                combo.setMinimumWidth(180)
                self._populate_combo(combo, cat, sev)
                combo.currentTextChanged.connect(
                    lambda text, c=cat, s=sev: self._on_sound_changed(c, s, text)
                )
                self._combos[(cat, sev)] = combo
                row.addWidget(combo, 1)

                preview_btn = QPushButton("▶")
                preview_btn.setFixedWidth(32)
                preview_btn.setToolTip(f"Preview {_CATEGORY_LABELS[cat]} / {_SEVERITY_LABELS[sev]} sound")
                preview_btn.clicked.connect(lambda _, c=cat, s=sev: self._preview(c, s))
                row.addWidget(preview_btn)

                container = QWidget()
                container.setLayout(row)
                form.addRow(f"{_SEVERITY_LABELS[sev]}:", container)

            root.addWidget(group)

        # ── Sounds folder ─────────────────────────────────────────────
        folder_btn = QPushButton("Open Sounds Folder")
        folder_btn.clicked.connect(self._open_sounds_folder)
        root.addWidget(folder_btn)

        root.addStretch(1)
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ------------------------------------------------------------------
    def _populate_combo(self, combo: QComboBox, category: str, severity: str) -> None:
        from notifications.services.sound_player import list_available_sounds, settings_key
        sounds = list_available_sounds()

        combo.blockSignals(True)
        combo.clear()
        combo.addItem(_NO_SOUND)
        for f in sounds:
            combo.addItem(f)

        saved = self._get(settings_key(category, severity))
        if saved and saved in sounds:
            combo.setCurrentText(saved)
        else:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)

    def _get(self, key: str):
        getter = getattr(self._bridge, "getSetting", None)
        if getter is None:
            return None
        try:
            return getter(key)
        except Exception:
            return None

    def _set(self, key: str, value) -> None:
        setter = getattr(self._bridge, "setSetting", None)
        if setter:
            try:
                setter(key, value)
            except Exception:
                pass

    def _make_separator(self) -> QWidget:
        from PySide6.QtWidgets import QFrame
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    def _on_threshold_changed(self, category: str, severity: str) -> None:
        self._set(f"notification.threshold.{category}", severity)
        try:
            from notifications.services.notifier import get_notifier
            get_notifier().set_threshold(category, severity)
        except Exception:
            pass

    def _on_sound_changed(self, category: str, severity: str, text: str) -> None:
        from notifications.services.sound_player import SoundPlayer, settings_key
        filename = None if text == _NO_SOUND else text
        self._set(settings_key(category, severity), filename)
        try:
            SoundPlayer.instance().set_sound(category, severity, filename)
        except Exception:
            pass

    def _on_volume_changed(self, value: int) -> None:
        try:
            from notifications.services.sound_player import SoundPlayer
            SoundPlayer.instance().set_volume(value)
        except Exception:
            pass

    def _preview(self, category: str, severity: str) -> None:
        combo = self._combos.get((category, severity))
        if combo is None:
            return
        text = combo.currentText()
        if text == _NO_SOUND:
            return
        try:
            from notifications.services.sound_player import SoundPlayer
            SoundPlayer.instance().preview(text)
        except Exception:
            pass

    def _open_sounds_folder(self) -> None:
        from notifications.services.sound_player import SOUNDS_DIR
        try:
            os.makedirs(SOUNDS_DIR, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(SOUNDS_DIR)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", SOUNDS_DIR])
            else:
                subprocess.Popen(["xdg-open", SOUNDS_DIR])
        except Exception:
            pass
