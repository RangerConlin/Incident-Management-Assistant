"""Settings dialog for weather module preferences."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..services.api_link import WeatherApiManager
from ..services.settings import weather_settings


class SettingsDialog(QDialog):
    """Provides configuration for weather polling and behaviour."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("weatherSettingsDialog")
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowFlag(Qt.Window)
        self.setWindowTitle("Settings: Weather Safety")
        self.resize(640, 480)
        self.api = WeatherApiManager.instance()
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form = QFormLayout()
        self.poll_interval = QSpinBox(self)
        self.poll_interval.setRange(1, 120)
        form.addRow("Polling interval (min)", self.poll_interval)

        self.alert_sound = QCheckBox("Alert sound", self)
        form.addRow(self.alert_sound)

        slider_row = QHBoxLayout()
        slider_row.addWidget(QLabel("Volume", self))
        self.alert_volume = QSlider(Qt.Horizontal, self)
        self.alert_volume.setRange(0, 100)
        slider_row.addWidget(self.alert_volume)
        form.addRow(slider_row)

        self.severity_filter = QComboBox(self)
        self.severity_filter.addItems(["All", "Severe", "Extreme"])
        form.addRow("Severity filter", self.severity_filter)

        self.duplicate_suppression = QSpinBox(self)
        self.duplicate_suppression.setRange(0, 240)
        form.addRow("Duplicate suppression (min)", self.duplicate_suppression)

        self.store_snapshots = QCheckBox("Store hourly snapshots (≈3 MB/week)", self)
        form.addRow(self.store_snapshots)

        self.role_override = QComboBox(self)
        self.role_override.addItems([
            "Safety Officer",
            "Incident Commander",
            "Planning Section Chief",
        ])
        form.addRow("Role allowed to override", self.role_override)

        self.timezone = QComboBox(self)
        self.timezone.addItems(["UTC", "Local"])
        form.addRow("Timezone", self.timezone)

        layout.addLayout(form)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        QWidget.setTabOrder(self.poll_interval, self.alert_sound)
        QWidget.setTabOrder(self.alert_sound, self.alert_volume)
        QWidget.setTabOrder(self.alert_volume, self.severity_filter)
        QWidget.setTabOrder(self.severity_filter, self.duplicate_suppression)
        QWidget.setTabOrder(self.duplicate_suppression, self.store_snapshots)
        QWidget.setTabOrder(self.store_snapshots, self.role_override)
        QWidget.setTabOrder(self.role_override, self.timezone)
        QWidget.setTabOrder(self.timezone, self.buttons.button(QDialogButtonBox.Save))

    def _load_settings(self) -> None:
        store = weather_settings()
        self.poll_interval.setValue(int(store.value("poll_interval", 10)))
        self.alert_sound.setChecked(bool(int(store.value("alert_sound", 1))))
        self.alert_volume.setValue(int(store.value("alert_volume", 75)))
        self.severity_filter.setCurrentText(store.value("severity_filter", "Severe"))
        self.duplicate_suppression.setValue(int(store.value("dup_suppression", 30)))
        self.store_snapshots.setChecked(bool(int(store.value("store_snapshots", 1))))
        self.role_override.setCurrentText(store.value("role_override", "Safety Officer"))
        self.timezone.setCurrentText(store.value("timezone", "UTC"))

    def _save(self) -> None:
        store = weather_settings()
        store.set_value("poll_interval", self.poll_interval.value())
        store.set_value("alert_sound", int(self.alert_sound.isChecked()))
        store.set_value("alert_volume", self.alert_volume.value())
        store.set_value("severity_filter", self.severity_filter.currentText())
        store.set_value("dup_suppression", self.duplicate_suppression.value())
        store.set_value("store_snapshots", int(self.store_snapshots.isChecked()))
        store.set_value("role_override", self.role_override.currentText())
        store.set_value("timezone", self.timezone.currentText())
        self.api.configure_polling(self.poll_interval.value())
        self.accept()


def show_window(parent: QWidget | None = None) -> SettingsDialog:
    dialog = SettingsDialog(parent)
    dialog.open()
    return dialog


__all__ = ["SettingsDialog", "show_window"]
