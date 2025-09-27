"""Notifications settings page."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QFormLayout, QSlider, QWidget

from ..binding import bind_checkbox, bind_slider


class NotificationsPage(QWidget):
    """Alerting and notification preferences."""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        sound_alerts = QCheckBox("Enable Sound Alerts")
        bind_checkbox(sound_alerts, bridge, "soundAlerts", True)
        layout.addRow(sound_alerts)

        volume = QSlider(Qt.Horizontal)
        volume.setRange(0, 100)
        bind_slider(volume, bridge, "volume", 75)
        layout.addRow("Volume:", volume)

        critical_override = QCheckBox("Critical Alerts Override Mute")
        bind_checkbox(critical_override, bridge, "criticalOverride", True)
        layout.addRow(critical_override)

        notify_tasks = QCheckBox("Notify on Task Updates")
        bind_checkbox(notify_tasks, bridge, "notifyOnTasks", True)
        layout.addRow(notify_tasks)
