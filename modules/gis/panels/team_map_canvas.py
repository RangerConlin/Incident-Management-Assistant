"""Shared Leaflet canvas for compact live team-location maps."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot, QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from modules.gis.services.team_symbols import TeamSymbolSpec, team_symbol_spec
from utils.incident_cache import incident_cache
from utils.styles import get_palette, subscribe_theme

logger = logging.getLogger(__name__)

_ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "leaflet"
_DEFAULT_CENTER = (39.8283, -98.5795)
_DEFAULT_ZOOM = 5
_DEFAULT_BASEMAP = "osm"

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


def _team_symbol_payload(symbol: TeamSymbolSpec) -> dict[str, Any]:
    return {
        "team_type": symbol.team_type,
        "label": symbol.label,
        "center_text": symbol.center_text,
        "fill_color": symbol.fill_color,
        "fill_highlight_color": symbol.fill_highlight_color,
        "fill_shadow_color": symbol.fill_shadow_color,
        "border_color": symbol.border_color,
        "border_shadow_color": symbol.border_shadow_color,
        "inner_ring_color": symbol.inner_ring_color,
        "text_color": symbol.text_color,
        "status_key": symbol.status_key,
        "icon_url": symbol.icon_url,
    }


def _map_html(center_lat: float, center_lon: float, zoom: int, basemap_key: str) -> str:
    basemap_config = json.dumps(_BASEMAPS)
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<link rel="stylesheet" href="leaflet.css" />
<style>
  html, body, #map {{ height: 100%; margin: 0; padding: 0; }}
  .team-marker-label {{
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid rgba(31, 41, 55, 0.22);
    border-radius: 4px;
    box-shadow: 0 1px 4px rgba(15, 23, 42, 0.22);
    color: #111827;
    font: 600 12px/1.2 Arial, sans-serif;
    padding: 3px 6px;
    white-space: nowrap;
  }}
  .team-marker-label::before {{ display: none; }}
  .team-symbol-wrapper {{ background: transparent; border: 0; }}
  .team-symbol {{
    align-items: center;
    background:
      linear-gradient(145deg, var(--team-fill-highlight) 0%, var(--team-fill) 54%, var(--team-fill-shadow) 100%);
    border: 5px solid var(--team-border);
    border-radius: 13px;
    box-shadow:
      inset 0 0 0 3px var(--team-inner-ring),
      inset 0 2px 4px var(--team-fill-highlight),
      inset 0 -3px 5px var(--team-fill-shadow),
      0 0 0 2px var(--team-border-shadow);
    box-sizing: border-box;
    color: var(--team-text);
    display: flex;
    font: 800 14px/1 Arial, sans-serif;
    height: 44px;
    justify-content: center;
    letter-spacing: 0;
    text-align: center;
    width: 44px;
  }}
  .team-symbol img {{
    display: block;
    height: 70%;
    object-fit: contain;
    width: 72%;
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
  var map = L.map('map').setView([{center_lat}, {center_lon}], {zoom});
  var basemapLayer = null;
  var markers = {{}};
  var mapBridge = null;
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
  function escapeHtml(value) {{
    return String(value || '').replace(/[&<>"']/g, function(ch) {{
      return {{ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }}[ch];
    }});
  }}
  function teamIcon(symbolSpec) {{
    var spec = symbolSpec || {{}};
    var fill = spec.fill_color || {json.dumps(get_palette()["accent"].name())};
    var fillHighlight = spec.fill_highlight_color || fill;
    var fillShadow = spec.fill_shadow_color || fill;
    var border = spec.border_color || {json.dumps(get_palette()["accent"].name())};
    var borderShadow = spec.border_shadow_color || border;
    var innerRing = spec.inner_ring_color || fill;
    var text = spec.text_color || {json.dumps(get_palette()["fg"].name())};
    var centerText = escapeHtml(spec.center_text || 'T');
    var label = escapeHtml(spec.label || 'Team');
    var body = centerText;
    if (spec.icon_url) {{
      body = '<img alt="" src="' + escapeHtml(spec.icon_url) + '" />';
    }}
    var html = '<div class="team-symbol" title="' + label + '" ' +
      'style="--team-fill:' + fill +
      ';--team-fill-highlight:' + fillHighlight +
      ';--team-fill-shadow:' + fillShadow +
      ';--team-border:' + border +
      ';--team-border-shadow:' + borderShadow +
      ';--team-inner-ring:' + innerRing +
      ';--team-text:' + text + ';">' +
      body + '</div>';
    return L.divIcon({{
      className: 'team-symbol-wrapper',
      html: html,
      iconSize: [44, 44],
      iconAnchor: [22, 22],
      popupAnchor: [0, -24]
    }});
  }}
  function upsertMarker(teamId, name, lat, lon, symbolSpecJson) {{
    var key = String(teamId);
    var symbolSpec = {{}};
    try {{ symbolSpec = JSON.parse(symbolSpecJson || '{{}}'); }} catch (err) {{ symbolSpec = {{}}; }}
    var icon = teamIcon(symbolSpec);
    if (markers[key]) {{
      markers[key].setLatLng([lat, lon]);
      markers[key].setIcon(icon);
    }} else {{
      markers[key] = L.marker([lat, lon], {{ icon: icon }}).addTo(map);
    }}
    markers[key].bindPopup(escapeHtml(name));
    markers[key].bindTooltip(escapeHtml(name), {{
      permanent: true,
      direction: 'top',
      offset: [0, -10],
      opacity: 1,
      className: 'team-marker-label'
    }});
    markers[key].off('click');
    markers[key].on('click', function() {{
      if (mapBridge && mapBridge.selectTeam) {{
        mapBridge.selectTeam(String(teamId));
      }}
    }});
  }}
  function removeMarker(teamId) {{
    var key = String(teamId);
    if (markers[key]) {{
      map.removeLayer(markers[key]);
      delete markers[key];
    }}
  }}
  function setBasemap(key) {{
    applyBasemap(key);
    return currentBasemapKey;
  }}
  function fitToMarkers() {{
    var coords = [];
    Object.keys(markers).forEach(function(key) {{
      coords.push(markers[key].getLatLng());
    }});
    if (!coords.length) {{ return false; }}
    map.fitBounds(L.latLngBounds(coords), {{ padding: [24, 24], maxZoom: 14 }});
    return true;
  }}
  applyBasemap(currentBasemapKey);
</script>
</body>
</html>"""


class _MapSelectionBridge(QObject):
    teamSelected = Signal(int)

    @Slot(str)
    def selectTeam(self, team_id: str) -> None:
        try:
            self.teamSelected.emit(int(team_id))
        except (TypeError, ValueError):
            return


class TeamMapCanvas(QWidget):
    """Bare Leaflet map + live team markers, for compact embedded views."""

    teamSelected = Signal(int)
    mapReady = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        center: tuple[float, float] | None = None,
        zoom: int = _DEFAULT_ZOOM,
        basemap_key: str = _DEFAULT_BASEMAP,
    ) -> None:
        super().__init__(parent)
        self._known_located_teams: set[int] = set()
        self._ready = False
        self._basemap_key = basemap_key if basemap_key in _BASEMAPS else _DEFAULT_BASEMAP

        incident = incident_cache.active_incident() or {}
        self.incident_center = center or (
            float(incident.get("latitude") or _DEFAULT_CENTER[0]),
            float(incident.get("longitude") or _DEFAULT_CENTER[1]),
        )

        self._bridge = _MapSelectionBridge(self)
        self._bridge.teamSelected.connect(self.teamSelected.emit)
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

        lat, lon = self.incident_center
        html = _map_html(lat, lon, zoom, self._basemap_key)
        base_url = QUrl(_ASSETS_DIR.as_uri() + "/")
        self._view.setHtml(html, base_url)

        incident_cache.changed.connect(self._on_cache_changed)
        self.destroyed.connect(lambda _=None: self._disconnect())
        subscribe_theme(self, lambda *_: self._refresh_team_markers())

    def _disconnect(self) -> None:
        try:
            incident_cache.changed.disconnect(self._on_cache_changed)
        except Exception:
            pass

    @property
    def ready(self) -> bool:
        return self._ready

    def _on_load_finished(self, ok: bool) -> None:
        if not ok:
            logger.warning("TeamMapCanvas: map HTML failed to load")
            return
        self._ready = True
        self._refresh_team_markers()
        self.mapReady.emit()

    def _on_cache_changed(self, collection: str, op: str, doc_id: str) -> None:
        if collection != "teams" or not self._ready:
            return
        if op == "deleted":
            return
        doc = incident_cache.get("teams", doc_id)
        if doc is not None:
            self._apply_team_doc(doc)

    def _refresh_team_markers(self) -> None:
        if not self._ready:
            return
        for doc in incident_cache.get_all("teams"):
            self._apply_team_doc(doc)

    def _apply_team_doc(self, doc: dict[str, Any]) -> None:
        team_id = doc.get("int_id")
        if team_id is None:
            return
        lat = doc.get("current_location_lat")
        lon = doc.get("current_location_lon")
        if lat is None or lon is None or doc.get("deleted"):
            if team_id in self._known_located_teams:
                self._known_located_teams.discard(team_id)
                self._run_js(f"removeMarker({json.dumps(str(team_id))});")
            return
        try:
            lat_value = float(lat)
            lon_value = float(lon)
        except (TypeError, ValueError):
            return
        name = doc.get("name") or f"Team {team_id}"
        self._known_located_teams.add(int(team_id))
        symbol = team_symbol_spec(doc.get("team_type"), doc.get("status"))
        self._run_js(
            "upsertMarker("
            f"{json.dumps(str(team_id))}, {json.dumps(name)}, {lat_value}, {lon_value}, "
            f"{json.dumps(json.dumps(_team_symbol_payload(symbol)))});"
        )

    def fit_visible(self, callback: Any | None = None) -> None:
        self._run_js("fitToMarkers();", callback=callback)

    def _run_js(self, script: str, callback: Any | None = None) -> None:
        page = self._view.page()
        if page is not None:
            if callback is None:
                page.runJavaScript(script)
            else:
                page.runJavaScript(script, 0, callback)


__all__ = ["TeamMapCanvas"]

