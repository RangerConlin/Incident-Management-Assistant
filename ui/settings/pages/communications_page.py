"""Communications settings page."""

from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QWidget

from ..binding import bind_checkbox, bind_combobox


class CommunicationsPage(QWidget):
    """Settings related to communication workflows."""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        mobile_app = QCheckBox("Enable Mobile App Integration")
        bind_checkbox(mobile_app, bridge, "mobileAppIntegration", False)
        layout.addRow(mobile_app)

        auto_ics205 = QCheckBox("Auto-generate ICS 205")
        bind_checkbox(auto_ics205, bridge, "autoGenerateICS205", True)
        layout.addRow(auto_ics205)

        verbosity = QComboBox()
        verbosity.addItems(["None", "Summary", "Full"])
        bind_combobox(verbosity, bridge, "commsLogVerbosity", 1)
        layout.addRow("Comms Log Verbosity:", verbosity)
