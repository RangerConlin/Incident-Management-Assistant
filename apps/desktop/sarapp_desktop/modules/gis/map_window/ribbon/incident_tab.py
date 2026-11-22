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
from modules.gis.map_window.operational_geometry_types import (
    OPERATIONAL_AREA_TYPES,
    OPERATIONAL_EVENT_AREA_TYPES,
    OPERATIONAL_EVENT_LINE_TYPES,
    OPERATIONAL_LINE_TYPES,
    OperationalGeometryType,
    primary_area_types,
    primary_line_types,
)
from styles.map_icons import (
    icon_buffer,
    icon_convert,
    icon_delete,
    icon_draw_arc,
    icon_draw_circle,
    icon_draw_line,
    icon_draw_point,
    icon_draw_polygon,
    icon_draw_rectangle,
    icon_draw_ring,
    icon_marker,
    icon_move,
    icon_search_grid,
    icon_search_pattern,
    icon_select,
    icon_task_area,
    icon_vertices,
)

if TYPE_CHECKING:
    from modules.gis.map_window.incident_map_window import IncidentMapWindow

_DRAW_TOOLS = [
    ("Point", "draw_point", icon_draw_point),
    ("Line", "draw_line", icon_draw_line),
    ("Arc", "draw_arc", icon_draw_arc),
    ("Polygon", "draw_polygon", icon_draw_polygon),
    ("Rectangle", "draw_rectangle", icon_draw_rectangle),
    ("Circle", "draw_circle", icon_draw_circle),
    ("Ring", "draw_ring", icon_draw_ring),
]


class IncidentTab(RibbonTabPage):
    def __init__(self, window: "IncidentMapWindow", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._window = window
        self.add_group(self._build_operational_points_group())
        self.add_group(
            self._build_operational_geometry_group(
                "Operational Lines",
                primary_line_types(),
                OPERATIONAL_LINE_TYPES,
                self._window.start_operational_line,
                event_catalog=OPERATIONAL_EVENT_LINE_TYPES,
                event_label="Event Lines",
            )
        )
        self.add_group(
            self._build_operational_geometry_group(
                "Operational Areas",
                primary_area_types(),
                OPERATIONAL_AREA_TYPES,
                self._window.start_operational_area,
                icon=icon_task_area(),
                event_catalog=OPERATIONAL_EVENT_AREA_TYPES,
                event_label="Event Areas",
            )
        )
        self.add_group(self._build_draw_group())
        self.add_group(self._build_edit_group())
        self.add_group(self._build_search_generators_group())
        self.add_group(self._build_convert_group())

    # -- Operational Points ------------------------------------------------
    def _build_operational_points_group(self) -> RibbonGroup:
        group = RibbonGroup("Operational Points", self, max_content_width=320)
        template_icon = icon_marker()
        for definition in primary_operational_point_types():
            group.add_button(
                definition.short_label or definition.display_name,
                icon=template_icon,
                tooltip=definition.display_name,
                on_click=lambda _=False, ft=definition.feature_type.value: self._window.start_operational_point(ft),
            )

        more_menu = QMenu(self)
        for definition in OPERATIONAL_POINT_TYPES:
            action = more_menu.addAction(template_icon, definition.display_name)
            action.triggered.connect(
                lambda _checked=False, ft=definition.feature_type.value: self._window.start_operational_point(ft)
            )
        more_button = group.add_menu_button("More", more_menu)
        more_button.setIcon(template_icon)
        return group

    # -- Operational Lines / Areas -------------------------------------------
    def _build_operational_geometry_group(
        self,
        title: str,
        primary: tuple[OperationalGeometryType, ...],
        catalog: tuple[OperationalGeometryType, ...],
        start,
        *,
        icon=None,
        event_catalog: tuple[OperationalGeometryType, ...] = (),
        event_label: str = "Event",
    ) -> RibbonGroup:
        group = RibbonGroup(title, self, max_content_width=280)
        for definition in primary:
            group.add_button(
                definition.short_label or definition.display_name,
                icon=icon,
                tooltip=definition.display_name,
                on_click=lambda _=False, ft=definition.feature_type.value: start(ft),
            )

        more_menu = QMenu(self)
        for definition in catalog:
            action = more_menu.addAction(definition.display_name)
            action.triggered.connect(lambda _checked=False, ft=definition.feature_type.value: start(ft))
        group.add_menu_button("More", more_menu)

        if event_catalog:
            event_menu = QMenu(self)
            section = None
            for definition in event_catalog:
                if definition.menu_section != section:
                    section = definition.menu_section
                    event_menu.addSection(section or "")
                action = event_menu.addAction(definition.display_name)
                action.triggered.connect(
                    lambda _checked=False, d=definition: start(d.feature_type.value, d.subtype)
                )
            group.add_menu_button(event_label, event_menu)
        return group

    # -- Draw -----------------------------------------------------------
    def _build_draw_group(self) -> RibbonGroup:
        group = RibbonGroup("Draw", self, max_content_width=320)
        buttons = {}
        for label, tool_key, icon_fn in _DRAW_TOOLS:
            buttons[tool_key] = group.add_button(
                label,
                icon=icon_fn(),
                checkable=True,
                on_click=lambda _=False, tk=tool_key: self._window.activate_draw_tool(tk),
            )

        def _sync_checked(new_tool: str) -> None:
            for tool_key, button in buttons.items():
                button.setChecked(tool_key == new_tool)

        self._window.map_canvas.toolChanged.connect(_sync_checked)
        return group

    # -- Edit -----------------------------------------------------------
    def _build_edit_group(self) -> RibbonGroup:
        group = RibbonGroup("Edit", self, max_content_width=260)
        group.add_button("Select", icon=icon_select(), checkable=True, on_click=lambda: self._window.map_canvas.activate_tool("select"))
        group.add_button("Vertices", icon=icon_vertices(), tooltip="Edit Vertices", on_click=self._window.on_edit_vertices)
        group.add_button("Move", icon=icon_move(), on_click=self._window.on_move_feature)
        group.add_button("Delete", icon=icon_delete(), on_click=self._window.on_delete_selected_feature)
        group.add_button("Buffer…", icon=icon_buffer(), on_click=self._window.open_buffer_dialog)
        return group

    # -- Search Generators (stub) --------------------------------------
    def _build_search_generators_group(self) -> RibbonGroup:
        group = RibbonGroup("Search Generators", self, max_content_width=180)
        group.add_button("Search Grid", icon=icon_search_grid(), on_click=lambda: self._coming_soon("Search Grid generator"))
        group.add_button("Search Pattern", icon=icon_search_pattern(), on_click=lambda: self._coming_soon("Search Pattern generator"))
        return group

    # -- Convert (stub) ---------------------------------------------------
    def _build_convert_group(self) -> RibbonGroup:
        group = RibbonGroup("Convert", self)
        group.add_button("Convert To…", icon=icon_convert(), on_click=lambda: self._coming_soon("Convert To"))
        return group

    def _coming_soon(self, feature_name: str) -> None:
        QMessageBox.information(self, feature_name, f"{feature_name} is coming soon.")
