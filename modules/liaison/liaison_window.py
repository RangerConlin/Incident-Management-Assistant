"""LiaisonWindow — tabbed dashboard for the Liaison module.

A single QMainWindow hosting a QTabWidget with six primary tabs (Agency
Directory, Contacts, Agency Status, Requests, Agreements, Liaison Log),
replacing the previous button-bar-opens-separate-windows pattern.
Reporting Board and Customer Requests & Feedback are not part of the new
six-tab mockup but remain reachable (existing callers depend on them) as
two additional tabs appended after the primary six.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QTabWidget, QWidget


class LiaisonWindow(QMainWindow):
    """Liaison dashboard: one window, one tab bar, six primary sections."""

    # Maps the section keys used by callers (main.py, overview panel, etc.)
    # to the tab's display title. "Agency Requests" is the historical name
    # for what the mockup now calls "Requests".
    _SECTION_ALIASES = {
        "Agency Requests": "Requests",
    }

    def __init__(self, incident_id: object | None = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._incident_id = incident_id

        self.setWindowTitle("Liaison")
        self.resize(1400, 850)
        self.setMinimumSize(1000, 650)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowFlags(Qt.Window)

        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)

        self._panels: dict[str, QWidget] = {}
        for title, factory_name in [
            ("Agency Directory", "get_agency_directory_panel"),
            ("Contacts", "get_contacts_panel"),
            ("Agency Status", "get_agency_status_panel"),
            ("Requests", "get_requests_panel"),
            ("Agreements", "get_agreements_panel"),
            ("Liaison Log", "get_liaison_log_panel"),
            ("Reporting Board", "get_reporting_panel"),
            ("Customer Requests & Feedback", "get_customer_panel"),
        ]:
            panel = self._build_panel(factory_name)
            self._panels[title] = panel
            self.tabs.addTab(panel, title)

    def _build_panel(self, factory_name: str) -> QWidget:
        from modules import liaison

        factory = getattr(liaison, factory_name)
        return factory(self._incident_id)

    def load_incident(self, incident_id: object | None) -> None:
        self._incident_id = incident_id
        for panel in self._panels.values():
            reload_fn = getattr(panel, "reload", None)
            if callable(reload_fn):
                try:
                    reload_fn()
                except Exception:
                    pass
            setattr(panel, "incident_id", incident_id)

    def switch_to_section(self, key: str) -> None:
        title = self._SECTION_ALIASES.get(key, key)
        panel = self._panels.get(title)
        if panel is None:
            return
        self.tabs.setCurrentWidget(panel)
