"""Data and storage settings page."""

from PySide6.QtWidgets import QCheckBox, QFormLayout, QSpinBox, QWidget

from ..binding import bind_checkbox, bind_spinbox


class DataStoragePage(QWidget):
    """Settings for data synchronization and backups."""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        local_sync = QCheckBox("Enable Local Sync Backup")
        bind_checkbox(local_sync, bridge, "localSyncBackup", True)
        layout.addRow(local_sync)

        cloud_fallback = QCheckBox("Enable Cloud Fallback if Local Fails")
        bind_checkbox(cloud_fallback, bridge, "cloudFallback", True)
        layout.addRow(cloud_fallback)

        interval = QSpinBox()
        interval.setRange(1, 60)
        bind_spinbox(interval, bridge, "autoBackupInterval", 15)
        layout.addRow("Auto-Backup Interval (minutes):", interval)
