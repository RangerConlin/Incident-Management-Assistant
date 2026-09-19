"""Incident ribbon tab: Operational Points, Draw, Edit, Search Generators (stub), Convert (stub)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMenu, QMessageBox, QWidget

from modules.gis.map_window.ribbon.ribbon_group import RibbonGroup
from modules.gis.map_window.ribbon.ribbon_tab_page import RibbonTabPage
from modules.gis.map_window.operational_point_types import (
    OPERATIONAL_POINT_TYPES,
    primary_operational_point_types,
)
from styles.map_icons import icon_marker

if TYPE_CHECKING:
    from modules.gis.map_window.incident_map_window import IncidentMapWindow

_DRAW_TOOLS = [
    ("Point", "draw_point"),
    ("Line", "draw_line"),
    ("Arc", "draw_arc"),
    ("Polygon", "draw_polygon"),
    ("Rectangle", "draw_rectangle"),
    ("Circle", "draw_circle"),
    ("Ring", "draw_ring"),
]


class IncidentTab(RibbonTabPage):
    def __init__(self, window: "IncidentMapWindow", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._window = window
        self.add_group(self._build_operational_points_group())
        self.add_group(self._build_draw_group())
        self.add_group(self._build_edit_group())
        self.add_group(self._build_search_generators_group())
        self.add_group(self._build_convert_group())

    # -- Operational Points ------------------------------------------------
    def _build_operational_points_group(self) -> RibbonGroup:
        group = RibbonGroup("Operational Points", self)
        template_icon = icon_marker()
        for definition in primary_operational_point_types():
            group.add_button(
                definition.short_label or definition.display_name,
                icon=template_icon,
                tooltip=definition.display_name,
                large=False,
                on_click=lambda _=False, ft=definition.feature_type.value: self._window.start_operational_point(ft),
            )

        more_menu = QMenu(self)
        for definition in OPERATIONAL_POINT_TYPES:
            action = more_menu.addAction(template_icon, definition.display_name)
            action.triggered.connect(
                lambda _checked=False, ft=definition.feature_type.value: self._window.start_operational_point(ft)
            )
        more_button = group.add_menu_button("More", more_menu, large=False)
        more_button.setIcon(template_icon)
        return group

    # -- Draw -----------------------------------------------------------
    def _build_draw_group(self) -> RibbonGroup:
        group = RibbonGroup("Draw", self)
        buttons = {}
        for label, tool_key in _DRAW_TOOLS:
            buttons[tool_key] = group.add_button(
                label, checkable=True, on_click=lambda _=False, tk=tool_key: self._window.activate_draw_tool(tk)
            )

        def _sync_checked(new_tool: str) -> None:
            for tool_key, button in buttons.items():
                button.setChecked(tool_key == new_tool)

        self._window.map_canvas.toolChanged.connect(_sync_checked)
        return group

    # -- Edit -----------------------------------------------------------
    def _build_edit_group(self) -> RibbonGroup:
        group = RibbonGroup("Edit", self)
        group.add_button("Select", checkable=True, large=False, on_click=lambda: self._window.map_canvas.activate_tool("select"))
        group.add_button("Vertices", tooltip="Edit Vertices", large=False, on_click=self._window.on_edit_vertices)
        group.add_button("Move", large=False, on_click=self._window.on_move_feature)
        group.add_button("Delete", large=False, on_click=self._window.on_delete_selected_feature)
        group.add_button("Buffer…", large=False, on_click=self._window.open_buffer_dialog)
        return group

    # -- Search Generators (stub) --------------------------------------
    def _build_search_generators_group(self) -> RibbonGroup:
        group = RibbonGroup("Search Generators", self)
        group.add_button("Search Grid", large=False, on_click=lambda: self._coming_soon("Search Grid generator"))
        group.add_button("Search Pattern", large=False, on_click=lambda: self._coming_soon("Search Pattern generator"))
        return group

    # -- Convert (stub) ---------------------------------------------------
    def _build_convert_group(self) -> RibbonGroup:
        group = RibbonGroup("Convert", self)
        group.add_button("Convert To…", large=False, on_click=lambda: self._coming_soon("Convert To"))
        return group

    def _coming_soon(self, feature_name: str) -> None:
        QMessageBox.information(self, feature_name, f"{feature_name} is coming soon.")
