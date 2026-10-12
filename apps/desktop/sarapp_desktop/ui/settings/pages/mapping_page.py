"""Mapping and GPS settings page."""

from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QWidget

from ..binding import bind_checkbox, bind_combobox


class MappingPage(QWidget):
    """Preferences for the mapping experience."""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        basemap = QComboBox()
        basemap.addItems(["Offline", "OpenStreetMap", "ESRI"])
        bind_combobox(basemap, bridge, "basemapSource", 0)
        layout.addRow("Basemap Source:", basemap)

        grid_overlay = QCheckBox("Enable Grid Overlay")
        bind_checkbox(grid_overlay, bridge, "gridOverlay", False)
        layout.addRow(grid_overlay)

        fog_of_war = QCheckBox("Enable Fog of War Visualization")
        bind_checkbox(fog_of_war, bridge, "fogOfWar", False)
        layout.addRow(fog_of_war)

        live_tracking = QCheckBox("Enable Live Tracking (Teams, Vehicles, Aircraft)")
        bind_checkbox(live_tracking, bridge, "liveTracking", True)
        layout.addRow(live_tracking)
