"""Page widgets used within the settings window."""

from .general_page import GeneralPage
from .incident_defaults_page import IncidentDefaultsPage
from .communications_page import CommunicationsPage
from .data_storage_page import DataStoragePage
from .mapping_page import MappingPage
from .personnel_page import PersonnelPage
from .theme_page import ThemePage
from .notifications_page import NotificationsPage
from .advanced_page import AdvancedPage
from .about_page import AboutPage

__all__ = [
    "GeneralPage",
    "IncidentDefaultsPage",
    "CommunicationsPage",
    "DataStoragePage",
    "MappingPage",
    "PersonnelPage",
    "ThemePage",
    "NotificationsPage",
    "AdvancedPage",
    "AboutPage",
]
