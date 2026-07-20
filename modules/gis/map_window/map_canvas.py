"""MapCanvas: general-purpose Leaflet map widget for the Incident Map window.

Adapted from modules/gis/panels/team_location_map_panel.py's QWebEngineView +
vendored-Leaflet + QWebChannel embedding pattern, but generalized for
multiple feature types, pan/select/zoom-box tools, an extent (back/forward)
stack, and draw/quick-add click handling. North-up only — no rotation
control or rotation state anywhere in this widget, ever (hard spec
requirement).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QSettings, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from modules.gis.map_window.tools.tool_controller import ToolController
from modules.gis.models.geometry_types import GeometryType
from modules.gis.models.spatial_feature import SpatialFeature
from utils import incident_context
from utils.incident_cache import incident_cache

logger = logging.getLogger(__name__)

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "panels" / "assets" / "leaflet"
_DEFAULT_CENTER = (39.8283, -98.5795)
_DEFAULT_ZOOM = 5
_DEFAULT_BASEMAP = "osm"
_VIEW_SETTINGS = QSettings("SARApp", "IncidentMap")

_BASEMAPS: dict[str, dict[str, Any]] = {
    "osm": {
        "label": "OpenStreetMap",
        "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "options": {"maxZoom": 19, "attribution": "&copy; OpenStreetMap contributors"},
    },
    "topo": {
        "label": "Topographic",
        "url": "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        "options": {
            "maxZoom": 17,
            "attribution": "Map data: &copy; OpenStreetMap contributors, SRTM | Map style: &copy; OpenTopoMap",
        },
    },
    "voyager": {
        "label": "Carto Voyager",
        "url": "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        "options": {
            "maxZoom": 20,
            "subdomains": "abcd",
            "attribution": "&copy; OpenStreetMap contributors &copy; CARTO",
        },
    },
}

TOOL_PAN = "pan"
TOOL_SELECT = "select"
TOOL_ZOOM_IN_BOX = "zoom_in_box"
TOOL_ZOOM_OUT_BOX = "zoom_out_box"


def _map_html(center_lat: float, center_lon: float, zoom: int, basemap_key: str) -> str:
    basemap_config = json.dumps(_BASEMAPS)
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<link rel="stylesheet" href="leaflet.css" />
<style>
  html, body, #map {{ height: 100%; margin: 0; padding: 0; }}
  .imw-feature-label {{
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid rgba(31, 41, 55, 0.22);
    border-radius: 4px;
    box-shadow: 0 1px 4px rgba(15, 23, 42, 0.22);
    color: #111827;
    font: 600 12px/1.2 Arial, sans-serif;
    padding: 3px 6px;
    white-space: nowrap;
  }}
  .imw-zoombox {{
    border: 2px dashed #2F80ED;
    background: rgba(47, 128, 237, 0.12);
    position: absolute;
  }}
</style>
</head>
<body>
<div id="map"></div>
<script src="leaflet.js"></script>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
  var basemapConfigs = {basemap_config};
  var currentBasemapKey = {json.dumps(basemap_key)};
  var map = L.map('map', {{ zoomControl: true, rotate: false }}).setView([{center_lat}, {center_lon}], {zoom});
  var basemapLayer = null;
  var featureLayers = {{}};
  var currentTool = 'pan';
  var drawVertices = [];
  var drawPreviewLayer = null;
  var mapBridge = null;
  var zoomBoxStart = null;
  var zoomBoxRect = null;

  new QWebChannel(qt.webChannelTransport, function(channel) {{
    mapBridge = channel.objects.mapBridge || null;
  }});

  function applyBasemap(key) {{
    var cfg = basemapConfigs[key] || basemapConfigs.osm;
    if (basemapLayer) {{ map.removeLayer(basemapLayer); }}
    basemapLayer = L.tileLayer(cfg.url, cfg.options);
    basemapLayer.addTo(map);
    currentBasemapKey = key in basemapConfigs ? key : 'osm';
  }}

  function setBasemap(key) {{ applyBasemap(key); return currentBasemapKey; }}

  function setTool(tool) {{
    currentTool = tool;
    drawVertices = [];
    if (drawPreviewLayer) {{ map.removeLayer(drawPreviewLayer); drawPreviewLayer = null; }}
    map.dragging.enable();
    if (tool === 'zoom_in_box' || tool === 'zoom_out_box') {{
      map.dragging.disable();
    }}
  }}

  map.on('mousedown', function(e) {{
    if (currentTool !== 'zoom_in_box' && currentTool !== 'zoom_out_box') {{ return; }}
    zoomBoxStart = e.latlng;
  }});
  map.on('mouseup', function(e) {{
    if (!zoomBoxStart) {{ return; }}
    var bounds = L.latLngBounds(zoomBoxStart, e.latlng);
    zoomBoxStart = null;
    if (currentTool === 'zoom_in_box') {{
      map.fitBounds(bounds);
    }} else if (currentTool === 'zoom_out_box') {{
      var c = map.getCenter();
      var z = Math.max(map.getMinZoom(), map.getZoom() - 2);
      map.setView(c, z);
    }}
  }});

  map.on('click', function(e) {{
    if (currentTool === 'select' || currentTool === 'pan') {{
      if (mapBridge && mapBridge.notifyMapClicked) {{
        mapBridge.notifyMapClicked(e.latlng.lat, e.latlng.lng);
      }}
      return;
    }}
    if (currentTool.indexOf('draw_') === 0) {{
      drawVertices.push([e.latlng.lat, e.latlng.lng]);
      if (drawPreviewLayer) {{ map.removeLayer(drawPreviewLayer); }}
      if (currentTool === 'draw_point') {{
        if (mapBridge && mapBridge.notifyDrawFinished) {{
          mapBridge.notifyDrawFinished(currentTool, JSON.stringify(drawVertices));
        }}
        drawVertices = [];
        return;
      }}
      drawPreviewLayer = L.polyline(drawVertices, {{ color: '#2F80ED', dashArray: '4 4' }}).addTo(map);
    }}
  }});

  map.on('dblclick', function(e) {{
    if (currentTool === 'draw_line' || currentTool === 'draw_polygon' || currentTool === 'draw_arc') {{
      if (drawVertices.length >= 2 && mapBridge && mapBridge.notifyDrawFinished) {{
        mapBridge.notifyDrawFinished(currentTool, JSON.stringify(drawVertices));
      }}
      drawVertices = [];
      if (drawPreviewLayer) {{ map.removeLayer(drawPreviewLayer); drawPreviewLayer = null; }}
    }}
  }});

  map.on('mousemove', function(e) {{
    if (mapBridge && mapBridge.notifyCursorMoved) {{
      mapBridge.notifyCursorMoved(e.latlng.lat, e.latlng.lng);
    }}
  }});

  map.on('moveend zoomend', function() {{
    if (mapBridge && mapBridge.notifyExtentChanged) {{
      var b = map.getBounds();
      mapBridge.notifyExtentChanged(b.getSouth(), b.getWest(), b.getNorth(), b.getEast(), map.getZoom());
    }}
  }});

  function finishActiveDraw() {{
    if (drawVertices.length >= 2 && mapBridge && mapBridge.notifyDrawFinished) {{
      mapBridge.notifyDrawFinished(currentTool, JSON.stringify(drawVertices));
    }}
    drawVertices = [];
    if (drawPreviewLayer) {{ map.removeLayer(drawPreviewLayer); drawPreviewLayer = null; }}
  }}

  function cancelDraw() {{
    drawVertices = [];
    if (drawPreviewLayer) {{ map.removeLayer(drawPreviewLayer); drawPreviewLayer = null; }}
  }}

  function upsertFeature(featureId, label, geometryType, coordsJson, styleColor) {{
    var coords = JSON.parse(coordsJson);
    if (featureLayers[featureId]) {{
      map.removeLayer(featureLayers[featureId]);
    }}
    var layer = null;
    var color = styleColor || '#2F80ED';
    if (geometryType === 'POINT') {{
      layer = L.circleMarker(coords[0], {{ radius: 7, color: color, fillColor: color, fillOpacity: 0.85 }});
    }} else if (geometryType === 'LINE') {{
      layer = L.polyline(coords, {{ color: color, weight: 3 }});
    }} else if (geometryType === 'POLYGON') {{
      layer = L.polygon(coords, {{ color: color, weight: 2, fillOpacity: 0.18 }});
    }}
    if (!layer) {{ return; }}
    layer.bindTooltip(label || '', {{ permanent: false, className: 'imw-feature-label' }});
    layer.on('click', function(evt) {{
      L.DomEvent.stopPropagation(evt);
      if (mapBridge && mapBridge.notifyFeatureClicked) {{ mapBridge.notifyFeatureClicked(String(featureId)); }}
    }});
    layer.on('contextmenu', function(evt) {{
      L.DomEvent.stopPropagation(evt);
      if (mapBridge && mapBridge.notifyFeatureRightClicked) {{
        mapBridge.notifyFeatureRightClicked(String(featureId), evt.latlng.lat, evt.latlng.lng);
      }}
    }});
    layer.addTo(map);
    featureLayers[featureId] = layer;
  }}

  function removeFeature(featureId) {{
    if (featureLayers[featureId]) {{
      map.removeLayer(featureLayers[featureId]);
      delete featureLayers[featureId];
    }}
  }}

  function highlightFeature(featureId) {{
    Object.keys(featureLayers).forEach(function(key) {{
      var layer = featureLayers[key];
      if (layer.setStyle) {{
        layer.setStyle({{ weight: (String(key) === String(featureId)) ? 5 : (layer._imwBaseWeight || 2) }});
      }}
    }});
  }}

  function zoomInMap() {{ map.zoomIn(); }}
  function zoomOutMap() {{ map.zoomOut(); }}
  function centerMap(lat, lon, zoom) {{
    if (typeof zoom === 'number') {{ map.setView([lat, lon], zoom); return; }}
    map.setView([lat, lon], map.getZoom());
  }}
  function fitBoundsMap(south, west, north, east) {{
    map.fitBounds(L.latLngBounds([south, west], [north, east]), {{ padding: [24, 24] }});
  }}
  function getMapState() {{
    var center = map.getCenter();
    return {{ center_lat: center.lat, center_lon: center.lng, zoom: map.getZoom(), basemap_key: currentBasemapKey }};
  }}

  applyBasemap(currentBasemapKey);
</script>
</body>
</html>"""


# QWebChannel only exposes @Slot-decorated methods as callable functions to
# JS — a raw Signal shows up as an object with a .connect() method, not
# something JS can invoke directly. So JS calls the notifyX() slots below,
# each of which just re-emits the matching Python-side Signal that the rest
# of this module already connects to.
class MapBridge(QObject):
    mapClicked = Signal(float, float)
    cursorMoved = Signal(float, float)
    featureClicked = Signal(str)
    featureRightClicked = Signal(str, float, float)
    drawFinished = Signal(str, str)
    extentChanged = Signal(float, float, float, float, int)

    @Slot(float, float)
    def notifyMapClicked(self, lat: float, lon: float) -> None:
        self.mapClicked.emit(lat, lon)

    @Slot(float, float)
    def notifyCursorMoved(self, lat: float, lon: float) -> None:
        self.cursorMoved.emit(lat, lon)

    @Slot(str)
    def notifyFeatureClicked(self, feature_id: str) -> None:
        self.featureClicked.emit(feature_id)

    @Slot(str, float, float)
    def notifyFeatureRightClicked(self, feature_id: str, lat: float, lon: float) -> None:
        self.featureRightClicked.emit(feature_id, lat, lon)

    @Slot(str, str)
    def notifyDrawFinished(self, tool_key: str, vertices_json: str) -> None:
        self.drawFinished.emit(tool_key, vertices_json)

    @Slot(float, float, float, float, int)
    def notifyExtentChanged(self, south: float, west: float, north: float, east: float, zoom: int) -> None:
        self.extentChanged.emit(south, west, north, east, zoom)


class MapCanvas(QWidget):
    """Central map widget: Leaflet view + tool state + extent history."""

    toolChanged = Signal(str)
    cursorPositionChanged = Signal(float, float)
    featureSelected = Signal(str)
    featureContextMenuRequested = Signal(str, float, float)
    drawCompleted = Signal(str, list)  # tool_key, [(lat, lon), ...]
    mapClickedForPlacement = Signal(float, float)
    extentChanged = Signal(float, float, float, float)  # south, west, north, east

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ready = False
        self._incident_id = str(incident_context.get_active_incident_id() or "default")
        self.tools = ToolController(default_tool=TOOL_PAN)
        self.tools.subscribe(self._on_tool_activated)

        self._extent_stack: list[tuple[float, float, float, float]] = []
        self._extent_index = -1
        self._suppress_extent_capture = False

        self._bridge = MapBridge(self)
        self._bridge.mapClicked.connect(self._on_map_clicked)
        self._bridge.cursorMoved.connect(self._on_cursor_moved)
        self._bridge.featureClicked.connect(self.featureSelected)
        self._bridge.featureRightClicked.connect(self.featureContextMenuRequested)
        self._bridge.drawFinished.connect(self._on_draw_finished)
        self._bridge.extentChanged.connect(self._on_extent_changed)

        self._web_channel = QWebChannel(self)
        self._web_channel.registerObject("mapBridge", self._bridge)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._view = QWebEngineView(self)
        self._view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        self._view.page().setWebChannel(self._web_channel)
        self._view.loadFinished.connect(self._on_load_finished)
        layout.addWidget(self._view)

        incident = incident_cache.active_incident() or {}
        self._incident_center = (
            float(incident.get("latitude") or _DEFAULT_CENTER[0]),
            float(incident.get("longitude") or _DEFAULT_CENTER[1]),
        )
        saved = self._load_saved_view()
        html = _map_html(saved["center_lat"], saved["center_lon"], saved["zoom"], saved["basemap_key"])
        base_url = QUrl(_ASSETS_DIR.as_uri() + "/")
        self._view.setHtml(html, base_url)

    # ------------------------------------------------------------------
    def _on_load_finished(self, ok: bool) -> None:
        if not ok:
            logger.warning("MapCanvas: map HTML failed to load")
            return
        self._ready = True

    def is_ready(self) -> bool:
        return self._ready

    # -- Tools ----------------------------------------------------------
    def activate_tool(self, tool: str) -> None:
        self.tools.activate(tool)

    def reset_tool(self) -> None:
        self.tools.reset()

    def _on_tool_activated(self, new_tool: str, _previous: str) -> None:
        self._run_js(f"setTool({json.dumps(new_tool)});")
        self.toolChanged.emit(new_tool)

    def _on_map_clicked(self, lat: float, lon: float) -> None:
        self.mapClickedForPlacement.emit(lat, lon)

    def _on_cursor_moved(self, lat: float, lon: float) -> None:
        self.cursorPositionChanged.emit(lat, lon)

    def _on_draw_finished(self, tool_key: str, vertices_json: str) -> None:
        try:
            raw = json.loads(vertices_json)
            vertices = [(float(pair[0]), float(pair[1])) for pair in raw]
        except (TypeError, ValueError, json.JSONDecodeError):
            return
        self.drawCompleted.emit(tool_key, vertices)
        self.reset_tool()

    def cancel_active_draw(self) -> None:
        self._run_js("cancelDraw();")

    # -- Basemap / zoom ---------------------------------------------------
    def set_basemap(self, key: str) -> None:
        if key not in _BASEMAPS:
            key = _DEFAULT_BASEMAP
        self._run_js(f"setBasemap({json.dumps(key)});", callback=lambda _=None: self._persist_view())

    def zoom_in(self) -> None:
        self._run_js("zoomInMap();")

    def zoom_out(self) -> None:
        self._run_js("zoomOutMap();")

    def center_on(self, lat: float, lon: float, zoom: int | None = None) -> None:
        zoom_arg = "null" if zoom is None else str(int(zoom))
        self._run_js(f"centerMap({lat}, {lon}, {zoom_arg});", callback=lambda _=None: self._persist_view())

    def fit_bounds(self, south: float, west: float, north: float, east: float) -> None:
        self._run_js(f"fitBoundsMap({south}, {west}, {north}, {east});")

    def center_on_incident(self) -> None:
        lat, lon = self._incident_center
        self.center_on(lat, lon, _DEFAULT_ZOOM)

    # -- Extent history ---------------------------------------------------
    def _on_extent_changed(self, south: float, west: float, north: float, east: float, _zoom: int) -> None:
        self.extentChanged.emit(south, west, north, east)
        if self._suppress_extent_capture:
            self._suppress_extent_capture = False
            return
        bounds = (south, west, north, east)
        # Truncate any "forward" history when a new manual navigation occurs.
        self._extent_stack = self._extent_stack[: self._extent_index + 1]
        self._extent_stack.append(bounds)
        self._extent_index = len(self._extent_stack) - 1
        self._persist_view()

    def go_to_previous_extent(self) -> None:
        if self._extent_index <= 0:
            return
        self._extent_index -= 1
        self._suppress_extent_capture = True
        south, west, north, east = self._extent_stack[self._extent_index]
        self.fit_bounds(south, west, north, east)

    def go_to_next_extent(self) -> None:
        if self._extent_index >= len(self._extent_stack) - 1:
            return
        self._extent_index += 1
        self._suppress_extent_capture = True
        south, west, north, east = self._extent_stack[self._extent_index]
        self.fit_bounds(south, west, north, east)

    # -- Features -----------------------------------------------------------
    def upsert_feature(self, feature: SpatialFeature, coords: list[tuple[float, float]], color: str = "#2F80ED") -> None:
        """coords are (lat, lon) pairs already parsed from geometry_wkt by the caller."""
        geometry_type = feature.geometry_type.value if isinstance(feature.geometry_type, GeometryType) else str(feature.geometry_type)
        self._run_js(
            "upsertFeature("
            f"{json.dumps(feature.id)}, {json.dumps(feature.label)}, {json.dumps(geometry_type)}, "
            f"{json.dumps(json.dumps(coords))}, {json.dumps(color)});"
        )

    def remove_feature(self, feature_id: int | str) -> None:
        self._run_js(f"removeFeature({json.dumps(str(feature_id))});")

    def highlight_feature(self, feature_id: int | str) -> None:
        self._run_js(f"highlightFeature({json.dumps(str(feature_id))});")

    # -- Persistence --------------------------------------------------------
    def _settings_prefix(self) -> str:
        return f"map_view/{self._incident_id}"

    def _load_saved_view(self) -> dict[str, Any]:
        prefix = self._settings_prefix()
        try:
            zoom = int(_VIEW_SETTINGS.value(f"{prefix}/zoom", _DEFAULT_ZOOM))
        except (TypeError, ValueError):
            zoom = _DEFAULT_ZOOM
        try:
            center_lat = float(_VIEW_SETTINGS.value(f"{prefix}/center_lat", self._incident_center[0]))
            center_lon = float(_VIEW_SETTINGS.value(f"{prefix}/center_lon", self._incident_center[1]))
        except (TypeError, ValueError):
            center_lat, center_lon = self._incident_center
        basemap_key = str(_VIEW_SETTINGS.value(f"{prefix}/basemap_key", _DEFAULT_BASEMAP) or _DEFAULT_BASEMAP)
        if basemap_key not in _BASEMAPS:
            basemap_key = _DEFAULT_BASEMAP
        return {"center_lat": center_lat, "center_lon": center_lon, "zoom": zoom, "basemap_key": basemap_key}

    def _persist_view(self) -> None:
        if not self._ready:
            return
        self._run_js("getMapState();", callback=self._save_view_state)

    def _save_view_state(self, state: Any) -> None:
        if not isinstance(state, dict):
            return
        try:
            center_lat = float(state.get("center_lat"))
            center_lon = float(state.get("center_lon"))
            zoom = int(state.get("zoom"))
        except (TypeError, ValueError):
            return
        basemap_key = str(state.get("basemap_key") or _DEFAULT_BASEMAP)
        prefix = self._settings_prefix()
        _VIEW_SETTINGS.setValue(f"{prefix}/center_lat", center_lat)
        _VIEW_SETTINGS.setValue(f"{prefix}/center_lon", center_lon)
        _VIEW_SETTINGS.setValue(f"{prefix}/zoom", zoom)
        _VIEW_SETTINGS.setValue(f"{prefix}/basemap_key", basemap_key)

    # -- JS bridge ------------------------------------------------------
    def _run_js(self, script: str, callback: Any | None = None) -> None:
        page = self._view.page()
        if page is None:
            return
        if callback is None:
            page.runJavaScript(script)
        else:
            page.runJavaScript(script, 0, callback)


BASEMAPS = _BASEMAPS
