"""Advanced settings page."""

from PySide6.QtWidgets import QCheckBox, QVBoxLayout, QWidget

from ..binding import bind_checkbox


class AdvancedPage(QWidget):
    """Advanced and experimental options."""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        sandbox = QCheckBox("Enable Sandbox Mode")
        bind_checkbox(sandbox, bridge, "sandboxMode", False)
        layout.addWidget(sandbox)

        ai_recommendations = QCheckBox("Enable AI Recommendations")
        bind_checkbox(ai_recommendations, bridge, "aiRecommendations", False)
        layout.addWidget(ai_recommendations)

        lan_collaboration = QCheckBox("Enable LAN Collaboration")
        bind_checkbox(lan_collaboration, bridge, "lanCollaboration", True)
        layout.addWidget(lan_collaboration)

        ui_debug = QCheckBox("Enable UI Debug Tools")
        bind_checkbox(ui_debug, bridge, "uiDebugTools", False)
        layout.addWidget(ui_debug)

        layout.addStretch(1)
