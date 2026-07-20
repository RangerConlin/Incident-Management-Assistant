"""IncidentMapWindow: the top-level ribbon + map canvas + bottom panel window.

Opened from main.py via `_open_panel(IncidentMapWindow(...), "Incident Map",
preferred_size=(1600, 1000))`. Not an ADS dock — a self-contained floating
top-level window with its own ribbon acting as the menu/toolbar, per the
plan's explicit exception to the "docked panel" convention.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from modules.gis.map_window.bottom_panel import BottomPanel
from modules.gis.map_window.contextual_strip import ContextualStrip
from modules.gis.map_window.map_canvas import MapCanvas
from modules.gis.map_window.ribbon.home_tab import HomeTab
from modules.gis.map_window.ribbon.incident_tab import IncidentTab
from modules.gis.map_window.ribbon.ribbon_group import RibbonGroup
from modules.gis.map_window.ribbon.ribbon_widget import RibbonWidget
from modules.gis.map_window.search.map_search import MapSearchController
from modules.gis.map_window.tools.buffer_dialog import BufferDialog
from modules.gis.map_window.tools.draw_tools import (
    line_to_wkt,
    points_to_wkt,
    polygon_to_wkt,
    rectangle_to_wkt,
)
from modules.gis.map_window.tools.quick_add_tool import QuickAddController
from modules.gis.models.feature_types import FeatureType
from modules.gis.models.geometry_types import GeometryType
from modules.gis.models.spatial_feature import SpatialFeature
from modules.gis.services.feature_registry import get_default_feature_registry
from modules.gis.services.geometry_service import GeometryBufferError, GeometryService
from modules.gis.services.spatial_repository import SpatialRepository
from utils.incident_cache import incident_cache

logger = logging.getLogger(__name__)


class IncidentMapWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Incident Map")
        # Keep this well under common laptop resolutions so the window can
        # always be shrunk/moved freely regardless of ribbon content width
        # (the ribbon itself scrolls horizontally when space is tight).
        self.setMinimumSize(900, 600)

        self.feature_registry = get_default_feature_registry()
        self.geometry_service = GeometryService(self.feature_registry)
        try:
            self.repository: SpatialRepository | None = SpatialRepository()
        except RuntimeError:
            self.repository = None
            logger.warning("IncidentMapWindow: no active incident, spatial repository disabled")

        self.search = MapSearchController(self)
        self.quick_add = (
            QuickAddController(self.repository, self.feature_registry) if self.repository else None
        )

        self._selected_feature: SpatialFeature | None = None
        self._features_by_id: dict[str, SpatialFeature] = {}
        self._pending_operational_point_type: str | None = None

        central = QWidget(self)
        self.setCentralWidget(central)
        outer_layout = QVBoxLayout(central)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.ribbon = RibbonWidget(self)
        outer_layout.addWidget(self.ribbon)

        self.contextual_strip = ContextualStrip(self)
        outer_layout.addWidget(self.contextual_strip)

        self.map_canvas = MapCanvas(self)

        self.home_tab = HomeTab(self)
        self.ribbon.add_tab("home", "Home", self.home_tab)
        self.incident_tab = IncidentTab(self)
        self.ribbon.add_tab("incident", "Incident", self.incident_tab)
        for stub_key, stub_title in (("file", "File"), ("layers", "Layers"), ("view", "View")):
            self.ribbon.add_tab(stub_key, stub_title, self._build_placeholder_tab(stub_title))
        self.ribbon.set_current_tab("home")

        self.bottom_panel = BottomPanel(self)

        splitter = QSplitter(Qt.Orientation.Vertical, self)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.map_canvas)
        splitter.addWidget(self.bottom_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        outer_layout.addWidget(splitter, 1)

        self._build_status_bar()
        self._wire_signals()

        escape_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        escape_shortcut.activated.connect(self._on_escape)

        self._refresh_feature_index()

    # ------------------------------------------------------------------
    def _build_placeholder_tab(self, title: str) -> QWidget:
        page = QWidget(self)
        from PySide6.QtWidgets import QHBoxLayout

        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        group = RibbonGroup(title, page)
        group.add_button("Coming soon", large=False)
        layout.addWidget(group)
        layout.addStretch(1)
        return page

    def _build_status_bar(self) -> None:
        bar = self.statusBar()
        self._cursor_label = QLabel("Cursor: -", self)
        self._scale_label = QLabel("Zoom: -", self)
        self._online_label = QLabel("Online", self)
        bar.addWidget(self._cursor_label)
        bar.addPermanentWidget(self._scale_label)
        bar.addPermanentWidget(self._online_label)

    def _wire_signals(self) -> None:
        self.map_canvas.cursorPositionChanged.connect(self._on_cursor_moved)
        self.map_canvas.extentChanged.connect(self._on_extent_changed)
        self.map_canvas.featureSelected.connect(self._on_feature_selected)
        self.map_canvas.featureContextMenuRequested.connect(self._on_feature_context_menu)
        self.map_canvas.drawCompleted.connect(self._on_draw_completed)
        self.map_canvas.mapClickedForPlacement.connect(self._on_map_click_for_placement)
        self.map_canvas.toolChanged.connect(self.contextual_strip.set_active_tool)

        self.search.localResultsReady.connect(self._on_local_search_results)
        self.search.geocodeResultReady.connect(self._on_geocode_result)

        self.bottom_panel.coordinateSubmitted.connect(lambda lat, lon: self.map_canvas.center_on(lat, lon, 14))
        self.bottom_panel.featureTableRowActivated.connect(self._on_feature_table_row_activated)

        self.contextual_strip.connect_open_details(self.on_open_feature_details)
        self.contextual_strip.connect_edit_vertices(self.on_edit_vertices)
        self.contextual_strip.connect_buffer(self.open_buffer_dialog)
        self.contextual_strip.connect_delete(self.on_delete_selected_feature)

    # -- Feature index / table ------------------------------------------
    def _refresh_feature_index(self) -> None:
        if self.repository is None:
            return
        features = self.repository.list_features()
        self._features_by_id = {str(f.id): f for f in features if f.id is not None}
        self.search.set_feature_index(features)
        rows = [
            (str(f.id), f.feature_type.value, f.label, f.layer_key)
            for f in features
        ]
        self.bottom_panel.set_feature_rows(rows)
        for feature in features:
            coords = self._geometry_wkt_to_latlon_coords(feature.geometry_wkt)
            if coords:
                self.map_canvas.upsert_feature(feature, coords)

    @staticmethod
    def _geometry_wkt_to_latlon_coords(geometry_wkt: str) -> list[tuple[float, float]]:
        from modules.gis.services.geometry_service import wkt_coords

        try:
            _, lonlat = wkt_coords(geometry_wkt)
        except Exception:
            return []
        return [(lat, lon) for lon, lat in lonlat]

    # -- Status bar -------------------------------------------------------
    def _on_cursor_moved(self, lat: float, lon: float) -> None:
        self._cursor_label.setText(f"Cursor: {lat:.5f}, {lon:.5f}")

    def _on_extent_changed(self, _south: float, _west: float, _north: float, _east: float) -> None:
        pass  # zoom/scale surfaced via toolChanged/basemap for this milestone

    # -- Search -----------------------------------------------------------
    def on_geocoder_search(self, text: str) -> None:
        if not text.strip():
            return
        self.search.search_geocoder(text)

    def _on_local_search_results(self, features: list[SpatialFeature]) -> None:
        self.bottom_panel.set_search_results({"Local Features": [f.label for f in features]})

    def _on_geocode_result(self, result) -> None:
        if result is None:
            self.bottom_panel.set_search_results({"Geocoder": ["No match found."]})
            return
        self.bottom_panel.set_search_results({"Geocoder": [result.address]})
        self.map_canvas.center_on(result.latitude, result.longitude, 15)

    def on_go_to_my_location(self) -> None:
        QMessageBox.information(
            self, "My Location", "Device location is not available on this workstation; use Coordinate Entry."
        )

    # -- Operational View ---------------------------------------------------
    def on_zoom_to_incident(self) -> None:
        self.map_canvas.center_on_incident()

    def on_zoom_to_teams(self) -> None:
        self._zoom_to_points(
            [
                (doc.get("current_location_lat"), doc.get("current_location_lon"))
                for doc in incident_cache.get_all("teams")
            ]
        )

    def on_zoom_to_tasks(self) -> None:
        self._zoom_to_points(
            [
                (doc.get("latitude"), doc.get("longitude"))
                for doc in incident_cache.get_all("tasks")
            ]
        )

    def _zoom_to_points(self, points: list[tuple[float | None, float | None]]) -> None:
        valid = [(lat, lon) for lat, lon in points if lat is not None and lon is not None]
        if not valid:
            return
        south = min(p[0] for p in valid)
        north = max(p[0] for p in valid)
        west = min(p[1] for p in valid)
        east = max(p[1] for p in valid)
        self.map_canvas.fit_bounds(south, west, north, east)

    # -- Quick Add ---------------------------------------------------------
    def arm_quick_add(self, kind: str) -> None:
        if self.quick_add is None:
            QMessageBox.warning(self, "Quick Add", "No active incident; cannot create features.")
            return
        self.quick_add.arm(kind, on_created=self._on_feature_created)
        self.map_canvas.activate_tool("select")

    def _on_map_click_for_placement(self, lat: float, lon: float) -> None:
        if self.quick_add is not None and self.quick_add.armed_kind is not None:
            self.quick_add.place_at(lat, lon)
            return
        if self._pending_operational_point_type is not None:
            self._create_operational_point(self._pending_operational_point_type, lat, lon)
            self._pending_operational_point_type = None

    def _on_feature_created(self, feature: SpatialFeature) -> None:
        self._refresh_feature_index()
        self.bottom_panel.append_log(f"Created {feature.feature_type.value}: {feature.label}")

    # -- Operational Points --------------------------------------------------
    def start_operational_point(self, feature_type_value: str) -> None:
        self._pending_operational_point_type = feature_type_value
        self.map_canvas.activate_tool("select")
        self.bottom_panel.append_log(f"Click the map to place a {feature_type_value.replace('_', ' ')}.")

    def _create_operational_point(self, feature_type_value: str, lat: float, lon: float) -> None:
        if self.repository is None:
            return
        try:
            feature_type = FeatureType(feature_type_value)
            registration = self.feature_registry.get(feature_type)
        except (ValueError, KeyError):
            return
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        feature = SpatialFeature(
            id=None,
            incident_id=self.repository.incident_id,
            feature_type=feature_type,
            feature_subtype=None,
            geometry_type=GeometryType.POINT,
            label=feature_type_value.replace("_", " ").title(),
            description=None,
            status="active",
            source_module="gis.map_window",
            source_record_type="operational_point",
            source_record_id="",
            geometry_wkt=f"POINT({lon:.7f} {lat:.7f})",
            centroid_lat=lat,
            centroid_lon=lon,
            bbox_min_lat=lat,
            bbox_min_lon=lon,
            bbox_max_lat=lat,
            bbox_max_lon=lon,
            elevation_m=None,
            start_time=now,
            end_time=None,
            is_planning_only=False,
            is_visible=True,
            is_locked=False,
            is_archived=False,
            layer_key=registration.default_layer_key,
            style_key=registration.default_style_key,
            created_at=now,
            updated_at=now,
            created_by=None,
            updated_by=None,
        )
        created = self.repository.create_feature(feature)
        self._on_feature_created(created)

    # -- Draw ---------------------------------------------------------------
    def activate_draw_tool(self, tool_key: str) -> None:
        self.map_canvas.activate_tool(tool_key)

    def _on_draw_completed(self, tool_key: str, vertices: list[tuple[float, float]]) -> None:
        if self.repository is None:
            return
        lonlat = [(lon, lat) for lat, lon in vertices]
        try:
            if tool_key in {"draw_point"}:
                geometry_wkt = points_to_wkt(lonlat)
                geometry_type = GeometryType.POINT
            elif tool_key in {"draw_line", "draw_arc"}:
                geometry_wkt = line_to_wkt(lonlat)
                geometry_type = GeometryType.LINE
            elif tool_key in {"draw_polygon", "draw_circle", "draw_ring"}:
                geometry_wkt = polygon_to_wkt(lonlat)
                geometry_type = GeometryType.POLYGON
            elif tool_key == "draw_rectangle":
                lats = [v[0] for v in vertices]
                lons = [v[1] for v in vertices]
                geometry_wkt = rectangle_to_wkt((min(lons), min(lats)), (max(lons), max(lats)))
                geometry_type = GeometryType.POLYGON
            else:
                return
        except ValueError:
            return

        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        lats = [v[0] for v in vertices]
        lons = [v[1] for v in vertices]
        feature = SpatialFeature(
            id=None,
            incident_id=self.repository.incident_id,
            feature_type=FeatureType.PLANNING_SKETCH,
            feature_subtype=tool_key,
            geometry_type=geometry_type,
            label=f"{tool_key.replace('draw_', '').title()} sketch",
            description=None,
            status="active",
            source_module="gis.map_window",
            source_record_type="drawing",
            source_record_id="",
            geometry_wkt=self.geometry_service.normalize_geometry_wkt(geometry_wkt),
            centroid_lat=sum(lats) / len(lats),
            centroid_lon=sum(lons) / len(lons),
            bbox_min_lat=min(lats),
            bbox_min_lon=min(lons),
            bbox_max_lat=max(lats),
            bbox_max_lon=max(lons),
            elevation_m=None,
            start_time=now,
            end_time=None,
            is_planning_only=True,
            is_visible=True,
            is_locked=False,
            is_archived=False,
            layer_key="planning_overlays",
            style_key="planning_sketch",
            created_at=now,
            updated_at=now,
            created_by=None,
            updated_by=None,
        )
        created = self.repository.create_feature(feature)
        self._on_feature_created(created)

    # -- Selection ------------------------------------------------------
    def _on_feature_selected(self, feature_id: str) -> None:
        feature = self._features_by_id.get(feature_id)
        self._selected_feature = feature
        self.contextual_strip.set_selection(feature)
        if feature is not None:
            self.map_canvas.highlight_feature(feature_id)

    def _on_feature_context_menu(self, feature_id: str, lat: float, lon: float) -> None:
        feature = self._features_by_id.get(feature_id)
        if feature is None:
            return
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        editable = feature.source_module == "gis.map_window" and not feature.is_locked
        menu.addAction("Open Details", self.on_open_feature_details)
        convert_action = menu.addAction("Convert To…")
        convert_action.triggered.connect(lambda: QMessageBox.information(self, "Convert To", "Coming soon."))
        edit_action = menu.addAction("Edit Vertices")
        edit_action.setEnabled(editable)
        edit_action.triggered.connect(self.on_edit_vertices)
        move_action = menu.addAction("Move")
        move_action.setEnabled(editable)
        move_action.triggered.connect(self.on_move_feature)
        menu.addAction("Duplicate", lambda: self._duplicate_feature(feature))
        menu.addAction("Change Style", lambda: QMessageBox.information(self, "Change Style", "Coming soon."))
        menu.addAction("Bring Forward", lambda: None)
        menu.addAction("Send Backward", lambda: None)
        menu.addAction("Add Buffer…", self.open_buffer_dialog)
        menu.addAction("Copy Coordinates", lambda: self._copy_coordinates(lat, lon))
        menu.addAction("Export Geometry", lambda: self._export_geometry(feature))
        delete_action = menu.addAction("Delete")
        delete_action.setEnabled(editable)
        delete_action.triggered.connect(self.on_delete_selected_feature)
        menu.exec(self.mapToGlobal(self.map_canvas.mapToParent(self.map_canvas.pos())))

    def on_clear_selection(self) -> None:
        self._selected_feature = None
        self.contextual_strip.set_selection(None)

    def on_zoom_to_selection(self) -> None:
        if self._selected_feature is None:
            return
        f = self._selected_feature
        if None in (f.bbox_min_lat, f.bbox_min_lon, f.bbox_max_lat, f.bbox_max_lon):
            return
        self.map_canvas.fit_bounds(f.bbox_min_lat, f.bbox_min_lon, f.bbox_max_lat, f.bbox_max_lon)

    def on_open_feature_details(self) -> None:
        if self._selected_feature is None:
            return
        QMessageBox.information(
            self,
            "Feature Details",
            f"{self._selected_feature.label}\nType: {self._selected_feature.feature_type.value}\n"
            f"Layer: {self._selected_feature.layer_key}",
        )

    def on_edit_vertices(self) -> None:
        QMessageBox.information(self, "Edit Vertices", "Vertex editing is coming soon.")

    def on_move_feature(self) -> None:
        QMessageBox.information(self, "Move", "Move is coming soon.")

    def on_delete_selected_feature(self) -> None:
        if self._selected_feature is None or self.repository is None or self._selected_feature.id is None:
            return
        confirm = QMessageBox.question(self, "Delete Feature", f"Delete '{self._selected_feature.label}'?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.repository.archive_feature(self._selected_feature.id)
        self.map_canvas.remove_feature(self._selected_feature.id)
        self._selected_feature = None
        self.contextual_strip.set_selection(None)
        self._refresh_feature_index()

    def _on_feature_table_row_activated(self, feature_id: str) -> None:
        self._on_feature_selected(feature_id)

    def _duplicate_feature(self, feature: SpatialFeature) -> None:
        if self.repository is None:
            return
        from datetime import datetime, timezone
        from dataclasses import replace

        now = datetime.now(timezone.utc)
        duplicate = replace(feature, id=None, label=f"{feature.label} (copy)", created_at=now, updated_at=now)
        created = self.repository.create_feature(duplicate)
        self._on_feature_created(created)

    def _copy_coordinates(self, lat: float, lon: float) -> None:
        from PySide6.QtGui import QGuiApplication

        QGuiApplication.clipboard().setText(f"{lat:.6f}, {lon:.6f}")

    def _export_geometry(self, feature: SpatialFeature) -> None:
        from PySide6.QtGui import QGuiApplication

        QGuiApplication.clipboard().setText(feature.geometry_wkt)

    # -- Buffer -------------------------------------------------------------
    def open_buffer_dialog(self) -> None:
        if self._selected_feature is None:
            QMessageBox.information(self, "Add Buffer", "Select a feature first.")
            return
        dialog = BufferDialog(self._selected_feature.geometry_wkt, self)
        if dialog.exec() != BufferDialog.DialogCode.Accepted:
            return
        results = dialog.result_wkt_list()
        if not results or self.repository is None:
            return
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        for wkt in results:
            feature = SpatialFeature(
                id=None,
                incident_id=self.repository.incident_id,
                feature_type=FeatureType.PLANNING_SKETCH,
                feature_subtype="buffer",
                geometry_type=GeometryType.POLYGON,
                label=f"Buffer of {self._selected_feature.label}",
                description=None,
                status="active",
                source_module="gis.map_window",
                source_record_type="buffer",
                source_record_id=str(self._selected_feature.id or ""),
                geometry_wkt=wkt,
                centroid_lat=self._selected_feature.centroid_lat,
                centroid_lon=self._selected_feature.centroid_lon,
                bbox_min_lat=None,
                bbox_min_lon=None,
                bbox_max_lat=None,
                bbox_max_lon=None,
                elevation_m=None,
                start_time=now,
                end_time=None,
                is_planning_only=True,
                is_visible=True,
                is_locked=False,
                is_archived=False,
                layer_key="planning_overlays",
                style_key="buffer",
                created_at=now,
                updated_at=now,
                created_by=None,
                updated_by=None,
            )
            try:
                created = self.repository.create_feature(feature)
                self._on_feature_created(created)
            except Exception:
                logger.exception("Failed to persist buffer feature")

    # -- Layers -----------------------------------------------------------
    def on_toggle_layer(self, layer_key: str, visible: bool) -> None:
        for feature in self._features_by_id.values():
            if feature.layer_key == layer_key and feature.id is not None:
                if visible:
                    coords = self._geometry_wkt_to_latlon_coords(feature.geometry_wkt)
                    if coords:
                        self.map_canvas.upsert_feature(feature, coords)
                else:
                    self.map_canvas.remove_feature(feature.id)

    def on_open_layer_manager(self) -> None:
        self.bottom_panel.show_tab("feature_table")

    # -- Escape -----------------------------------------------------------
    def _on_escape(self) -> None:
        self.map_canvas.reset_tool()
        self.map_canvas.cancel_active_draw()
        if self.quick_add is not None:
            self.quick_add.disarm()
        self._pending_operational_point_type = None
