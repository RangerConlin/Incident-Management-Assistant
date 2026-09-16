"""Home ribbon tab: Navigation, Find/Go To, Operational View, Quick Add, Selection, Map Utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QLineEdit, QMenu, QToolButton, QWidget

from modules.gis.map_window.map_canvas import BASEMAPS, TOOL_PAN, TOOL_SELECT, TOOL_ZOOM_IN_BOX, TOOL_ZOOM_OUT_BOX
from modules.gis.map_window.ribbon.ribbon_group import RibbonGroup
from modules.gis.map_window.ribbon.ribbon_tab_page import RibbonTabPage
from modules.gis.services.layer_registry import get_default_layer_registry
from styles.map_icons import (
    icon_clue,
    icon_coordinate_entry,
    icon_hazard,
    icon_marker,
    icon_measure,
    icon_my_location,
    icon_next_extent,
    icon_pan,
    icon_prev_extent,
    icon_search,
    icon_select,
    icon_task_area,
    icon_zoom_in,
    icon_zoom_out,
)

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

    def _make_icon_only(self, button: QToolButton) -> QToolButton:
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setFixedSize(QSize(32, 24))
        return button

    # -- Navigation -------------------------------------------------------
    def _build_navigation_group(self) -> RibbonGroup:
        group = RibbonGroup("Navigation", self, max_content_width=240)
        canvas = self._window.map_canvas

        pan_btn = self._make_icon_only(
            group.add_button(
                "Pan",
                icon=icon_pan(),
                checkable=True,
                on_click=lambda: canvas.activate_tool(TOOL_PAN),
                large=False,
            )
        )
        select_btn = self._make_icon_only(
            group.add_button(
                "Select",
                icon=icon_select(),
                checkable=True,
                on_click=lambda: canvas.activate_tool(TOOL_SELECT),
                large=False,
            )
        )
        zoom_in_btn = self._make_icon_only(
            group.add_button(
                "Zoom In",
                icon=icon_zoom_in(),
                checkable=True,
                tooltip="Zoom in by drawing a box",
                on_click=lambda: canvas.activate_tool(TOOL_ZOOM_IN_BOX),
                large=False,
            )
        )
        zoom_out_btn = self._make_icon_only(
            group.add_button(
                "Zoom Out",
                icon=icon_zoom_out(),
                checkable=True,
                tooltip="Zoom out by drawing a box",
                on_click=lambda: canvas.activate_tool(TOOL_ZOOM_OUT_BOX),
                large=False,
            )
        )
        self._make_icon_only(
            group.add_button(
                "Prev",
                icon=icon_prev_extent(),
                tooltip="Previous extent",
                on_click=canvas.go_to_previous_extent,
                large=False,
            )
        )
        self._make_icon_only(
            group.add_button(
                "Next",
                icon=icon_next_extent(),
                tooltip="Next extent",
                on_click=canvas.go_to_next_extent,
                large=False,
            )
        )

        tool_buttons = {TOOL_PAN: pan_btn, TOOL_SELECT: select_btn, TOOL_ZOOM_IN_BOX: zoom_in_btn, TOOL_ZOOM_OUT_BOX: zoom_out_btn}

        def _sync_checked(new_tool: str) -> None:
            for tool_key, button in tool_buttons.items():
                button.setChecked(tool_key == new_tool)

        canvas.toolChanged.connect(_sync_checked)
        pan_btn.setChecked(True)
        return group

    # -- Find / Go To -------------------------------------------------------
    def _build_find_group(self) -> RibbonGroup:
        group = RibbonGroup("Find / Go To", self, max_content_width=330)
        search_edit = QLineEdit(self)
        search_edit.setPlaceholderText("Search features or address…")
        search_edit.setMinimumWidth(160)
        search_edit.textEdited.connect(self._window.search.query_local_debounced)
        search_edit.returnPressed.connect(lambda: self._window.on_geocoder_search(search_edit.text()))
        group.add_widget(search_edit)

        self._make_icon_only(
            group.add_button(
                "Search",
                icon=icon_search(),
                on_click=lambda: self._window.on_geocoder_search(search_edit.text()),
                large=False,
            )
        )
        self._make_icon_only(
            group.add_button(
                "Coords",
                icon=icon_coordinate_entry(),
                tooltip="Coordinate Entry",
                on_click=lambda: self._window.bottom_panel.show_tab("coordinates"),
                large=False,
            )
        )
        self._make_icon_only(
            group.add_button(
                "Location",
                icon=icon_my_location(),
                tooltip="My Location",
                on_click=self._window.on_go_to_my_location,
                large=False,
            )
        )
        return group

    # -- Operational View -----------------------------------------------------
    def _build_operational_view_group(self) -> RibbonGroup:
        group = RibbonGroup("Operational View", self, max_content_width=280)
        group.add_button("Incident", tooltip="Incident Extent", on_click=self._window.on_zoom_to_incident, large=False)
        group.add_button("Teams", tooltip="Teams Extent", on_click=self._window.on_zoom_to_teams, large=False)
        group.add_button("Tasks", tooltip="Tasks Extent", on_click=self._window.on_zoom_to_tasks, large=False)
        return group

    # -- Quick Add -----------------------------------------------------------
    def _build_quick_add_group(self) -> RibbonGroup:
        group = RibbonGroup("Quick Add", self, max_content_width=160)
        self._make_icon_only(group.add_button("Marker", icon=icon_marker(), on_click=lambda: self._window.arm_quick_add("marker"), large=False))
        self._make_icon_only(group.add_button("Hazard", icon=icon_hazard(), on_click=lambda: self._window.arm_quick_add("hazard"), large=False))
        self._make_icon_only(group.add_button("Clue", icon=icon_clue(), on_click=lambda: self._window.arm_quick_add("clue"), large=False))
        self._make_icon_only(
            group.add_button(
                "Task Area",
                icon=icon_task_area(),
                on_click=lambda: self._window.arm_quick_add("task_area"),
                large=False,
            )
        )
        return group

    # -- Selection -------------------------------------------------------
    def _build_selection_group(self) -> RibbonGroup:
        group = RibbonGroup("Selection", self, max_content_width=240)
        group.add_button("Clear", tooltip="Clear Selection", on_click=self._window.on_clear_selection, large=False)
        group.add_button("Zoom", tooltip="Zoom to Selection", on_click=self._window.on_zoom_to_selection, large=False)
        return group

    # -- Map Utilities -----------------------------------------------------
    def _build_map_utilities_group(self) -> RibbonGroup:
        group = RibbonGroup("Map Utilities", self, max_content_width=270)
        self._make_icon_only(group.add_button("Measure", icon=icon_measure(), checkable=True, large=False))

        basemap_menu = QMenu(self)
        for key, config in BASEMAPS.items():
            action = basemap_menu.addAction(str(config["label"]))
            action.triggered.connect(lambda _checked=False, k=key: self._window.map_canvas.set_basemap(k))
        group.add_menu_button("Basemap", basemap_menu, large=False)

        layers_menu = QMenu(self)
        for layer in self._layer_registry.list_layers():
            action = layers_menu.addAction(layer.name)
            action.setCheckable(True)
            action.setChecked(True)
            action.toggled.connect(lambda checked, lk=layer.layer_key: self._window.on_toggle_layer(lk, checked))
        layers_menu.addSeparator()
        open_manager_action = layers_menu.addAction("Open Layer Manager…")
        open_manager_action.triggered.connect(self._window.on_open_layer_manager)
        group.add_menu_button("Layers", layers_menu, large=False)
        return group
