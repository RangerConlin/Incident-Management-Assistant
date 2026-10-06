"""General settings page."""

from PySide6.QtWidgets import QComboBox, QFormLayout, QWidget

from ..binding import bind_combobox
from utils.timefmt import (
    DISPLAY_TIMEZONE_SETTING,
    SYSTEM_TIMEZONE_KEY,
    display_timezone_options,
)


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

        time_zone = QComboBox()
        for key, label in display_timezone_options():
            time_zone.addItem(label, key)
        try:
            current_key = str(bridge.getSetting(DISPLAY_TIMEZONE_SETTING) or SYSTEM_TIMEZONE_KEY)
        except Exception:
            current_key = SYSTEM_TIMEZONE_KEY
        current_index = time_zone.findData(current_key)
        time_zone.setCurrentIndex(current_index if current_index >= 0 else 0)
        time_zone.currentIndexChanged.connect(
            lambda _idx, combo=time_zone: bridge.setSetting(
                DISPLAY_TIMEZONE_SETTING,
                combo.currentData(),
            )
        )
        layout.addRow("Display Time Zone:", time_zone)

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
