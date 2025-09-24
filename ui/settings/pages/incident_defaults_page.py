"""Incident defaults settings page."""

from PySide6.QtWidgets import QCheckBox, QVBoxLayout, QWidget

from ..binding import bind_checkbox


class IncidentDefaultsPage(QWidget):
    """Configuration for default incident behaviors."""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        auto_fill = QCheckBox("Auto-fill ICS Forms")
        bind_checkbox(auto_fill, bridge, "autoFillForms", True)
        layout.addWidget(auto_fill)

        auto_assign = QCheckBox("Auto-assign Equipment on Status Change")
        bind_checkbox(auto_assign, bridge, "autoAssignEquipment", True)
        layout.addWidget(auto_assign)

        auto_available = QCheckBox('Auto-set Personnel Status to "Available" on Check-In')
        bind_checkbox(auto_available, bridge, "autoSetAvailable", True)
        layout.addWidget(auto_available)

        auto_demobilize = QCheckBox('Demobilized = Status Change to "Demobilized"')
        bind_checkbox(auto_demobilize, bridge, "autoDemobilize", False)
        layout.addWidget(auto_demobilize)

        filter_active = QCheckBox("Show Only Active Incidents by Default")
        bind_checkbox(filter_active, bridge, "filterActiveIncidents", True)
        layout.addWidget(filter_active)

        layout.addStretch(1)
