"""General settings page."""

from PySide6.QtWidgets import QComboBox, QFormLayout, QWidget

from ..binding import bind_combobox


class GeneralPage(QWidget):
    """Page for general application preferences."""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        language = QComboBox()
        language.addItems(["English", "Spanish", "French"])
        bind_combobox(language, bridge, "languageIndex", 0)
        layout.addRow("Language:", language)

        date_format = QComboBox()
        date_format.addItems(["MM/DD/YYYY", "DD/MM/YYYY", "YYYY-MM-DD"])
        bind_combobox(date_format, bridge, "dateFormatIndex", 0)
        layout.addRow("Date Format:", date_format)

        units = QComboBox()
        units.addItems(["Imperial", "Metric"])
        bind_combobox(units, bridge, "unitIndex", 0)
        layout.addRow("Units:", units)

        startup = QComboBox()
        startup.addItems([
            "Prompt for Incident",
            "Load Last Incident",
            "Create New Incident",
        ])
        bind_combobox(startup, bridge, "startupBehaviorIndex", 0)
        layout.addRow("Startup Behavior:", startup)
