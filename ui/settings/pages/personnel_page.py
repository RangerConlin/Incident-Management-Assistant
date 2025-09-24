"""Personnel and teams settings page."""

from PySide6.QtWidgets import QCheckBox, QVBoxLayout, QWidget

from ..binding import bind_checkbox


class PersonnelPage(QWidget):
    """Team management preferences."""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        clear_assignment = QCheckBox('Auto-clear Assignment on "Out of Service"')
        bind_checkbox(clear_assignment, bridge, "clearAssignmentOutOfService", True)
        layout.addWidget(clear_assignment)

        filter_no_show = QCheckBox('Filter "No Show" by Default')
        bind_checkbox(filter_no_show, bridge, "filterNoShow", False)
        layout.addWidget(filter_no_show)

        team_templates = QCheckBox("Enable Team Templates")
        bind_checkbox(team_templates, bridge, "teamTemplatesEnabled", True)
        layout.addWidget(team_templates)

        layout.addStretch(1)
