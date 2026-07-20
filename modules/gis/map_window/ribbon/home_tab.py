"""Home ribbon tab: Navigation, Find/Go To, Operational View, Quick Add, Selection, Map Utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QMenu, QWidget

from modules.gis.map_window.map_canvas import BASEMAPS, TOOL_PAN, TOOL_SELECT, TOOL_ZOOM_IN_BOX, TOOL_ZOOM_OUT_BOX
from modules.gis.map_window.ribbon.ribbon_group import RibbonGroup
from modules.gis.map_window.ribbon.ribbon_tab_page import RibbonTabPage
from modules.gis.services.layer_registry import get_default_layer_registry

if TYPE_CHECKING:
    from modules.gis.map_window.incident_map_window import IncidentMapWindow


class HomeTab(RibbonTabPage):
    def __init__(self, window: "IncidentMapWindow", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._window = window
        self._layer_registry = get_default_layer_registry()

        self.add_group(self._build_navigation_group())
        self.add_group(self._build_find_group())
        self.add_group(self._build_operational_view_group())
        self.add_group(self._build_quick_add_group())
        self.add_group(self._build_selection_group())
        self.add_group(self._build_map_utilities_group())

    # -- Navigation -------------------------------------------------------
    def _build_navigation_group(self) -> RibbonGroup:
        group = RibbonGroup("Navigation", self)
        canvas = self._window.map_canvas

        pan_btn = group.add_button("Pan", icon_text="✥", checkable=True, on_click=lambda: canvas.activate_tool(TOOL_PAN))
        select_btn = group.add_button("Select", icon_text="⬚", checkable=True, on_click=lambda: canvas.activate_tool(TOOL_SELECT))
        zoom_in_btn = group.add_button(
            "Zoom In Box", icon_text="🔍+", checkable=True, on_click=lambda: canvas.activate_tool(TOOL_ZOOM_IN_BOX)
        )
        zoom_out_btn = group.add_button(
            "Zoom Out Box", icon_text="🔍-", checkable=True, on_click=lambda: canvas.activate_tool(TOOL_ZOOM_OUT_BOX)
        )
        group.add_button("Prev Extent", icon_text="◀", on_click=canvas.go_to_previous_extent)
        group.add_button("Next Extent", icon_text="▶", on_click=canvas.go_to_next_extent)

        tool_buttons = {TOOL_PAN: pan_btn, TOOL_SELECT: select_btn, TOOL_ZOOM_IN_BOX: zoom_in_btn, TOOL_ZOOM_OUT_BOX: zoom_out_btn}

        def _sync_checked(new_tool: str) -> None:
            for tool_key, button in tool_buttons.items():
                button.setChecked(tool_key == new_tool)

        canvas.toolChanged.connect(_sync_checked)
        pan_btn.setChecked(True)
        return group

    # -- Find / Go To -------------------------------------------------------
    def _build_find_group(self) -> RibbonGroup:
        group = RibbonGroup("Find / Go To", self)
        search_edit = QLineEdit(self)
        search_edit.setPlaceholderText("Search features or address…")
        search_edit.setMinimumWidth(90)
        search_edit.textEdited.connect(self._window.search.query_local_debounced)
        search_edit.returnPressed.connect(lambda: self._window.on_geocoder_search(search_edit.text()))
        group.add_widget(search_edit)

        group.add_button("Search", icon_text="🔎", on_click=lambda: self._window.on_geocoder_search(search_edit.text()))
        group.add_button("Coordinate Entry", icon_text="⌖", on_click=lambda: self._window.bottom_panel.show_tab("coordinates"))
        group.add_button("My Location", icon_text="📍", on_click=self._window.on_go_to_my_location)
        return group

    # -- Operational View -----------------------------------------------------
    def _build_operational_view_group(self) -> RibbonGroup:
        group = RibbonGroup("Operational View", self)
        group.add_button("Incident Extent", on_click=self._window.on_zoom_to_incident, large=False)
        group.add_button("Teams Extent", on_click=self._window.on_zoom_to_teams, large=False)
        group.add_button("Tasks Extent", on_click=self._window.on_zoom_to_tasks, large=False)
        return group

    # -- Quick Add -----------------------------------------------------------
    def _build_quick_add_group(self) -> RibbonGroup:
        group = RibbonGroup("Quick Add", self)
        group.add_button("Marker", icon_text="📌", on_click=lambda: self._window.arm_quick_add("marker"))
        group.add_button("Hazard", icon_text="⚠", on_click=lambda: self._window.arm_quick_add("hazard"))
        group.add_button("Clue", icon_text="🔎", on_click=lambda: self._window.arm_quick_add("clue"))
        group.add_button("Task Area", icon_text="▦", on_click=lambda: self._window.arm_quick_add("task_area"))
        return group

    # -- Selection -------------------------------------------------------
    def _build_selection_group(self) -> RibbonGroup:
        group = RibbonGroup("Selection", self)
        group.add_button("Clear Selection", on_click=self._window.on_clear_selection, large=False)
        group.add_button("Zoom to Selection", on_click=self._window.on_zoom_to_selection, large=False)
        return group

    # -- Map Utilities -----------------------------------------------------
    def _build_map_utilities_group(self) -> RibbonGroup:
        group = RibbonGroup("Map Utilities", self)
        group.add_button("Measure", icon_text="📏", checkable=True)

        basemap_menu = QMenu(self)
        for key, config in BASEMAPS.items():
            action = basemap_menu.addAction(str(config["label"]))
            action.triggered.connect(lambda _checked=False, k=key: self._window.map_canvas.set_basemap(k))
        group.add_menu_button("Basemap", basemap_menu)

        layers_menu = QMenu(self)
        for layer in self._layer_registry.list_layers():
            action = layers_menu.addAction(layer.name)
            action.setCheckable(True)
            action.setChecked(True)
            action.toggled.connect(lambda checked, lk=layer.layer_key: self._window.on_toggle_layer(lk, checked))
        layers_menu.addSeparator()
        open_manager_action = layers_menu.addAction("Open Layer Manager…")
        open_manager_action.triggered.connect(self._window.on_open_layer_manager)
        group.add_menu_button("Layers", layers_menu)
        return group
