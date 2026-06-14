from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .panels import HastyToolsPanel, InitialOverviewPanel

__all__ = ["get_hasty_panel", "get_initialresponse_panel"]


class InitialResponseWorkspace(QWidget):
    def __init__(self, incident_id: object | None = None, start_tab: str = "overview", parent: QWidget | None = None):
        super().__init__(parent)
        del incident_id
        self.resize(1000, 800)
        self.setMinimumSize(1000, 800)
        self._tabs = QTabWidget()
        self._overview = InitialOverviewPanel(
            open_hasty=lambda: self._tabs.setCurrentIndex(1),
        )
        self._hasty = HastyToolsPanel()
        self._tabs.addTab(self._overview, "Overview")
        self._tabs.addTab(self._hasty, "Early Tasking")

        start_index = {"overview": 0, "hasty": 1, "reflex": 1}.get(start_tab, 0)
        self._tabs.setCurrentIndex(start_index)

        layout = QVBoxLayout(self)
        layout.addWidget(self._tabs)


def get_hasty_panel(incident_id: object | None = None) -> QWidget:
    return InitialResponseWorkspace(incident_id=incident_id, start_tab="hasty")

def get_initialresponse_panel(incident_id: object | None = None) -> QWidget:
    return InitialResponseWorkspace(incident_id=incident_id, start_tab="overview")
