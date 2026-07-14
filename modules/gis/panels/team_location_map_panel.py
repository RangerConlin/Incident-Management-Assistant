"""Team-location map panel — GIS module Phase 1 (see modules/gis/DEVELOPER_NOTE.md
and tracking_plan.md in ICS-Mobile-App for the full design).

Renders a Leaflet/OpenStreetMap basemap with pan/zoom and one marker per team,
sourced from mobile GPS pings (see data/db/sarapp_db/api/routers/mobile_location.py
on the server side). No drawing tools, no spatial_features wiring, no
breadcrumb trail — only each team's last-known position. This panel is meant
as the permanent foundation later GIS-module phases extend (assignment-area
drawing, spatial-feature layers), not a throwaway MVP widget.

All data comes from IncidentCache, which already mirrors the `teams`
collection live over the incident's WebSocket feed — no separate network
calls are made here, per incident_cache.py's own "panels should read from
this cache" convention. The leader-preference logic that decides which
device's ping wins is entirely server-side; this panel just displays
whatever current_location_* fields land on each team's document.

Leaflet (vendored under assets/leaflet/, BSD-2-Clause) is loaded locally
rather than from a CDN so the map still renders without outbound internet —
only the OpenStreetMap tile imagery itself requires a live connection.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from utils.incident_cache import incident_cache

logger = logging.getLogger(__name__)

_ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "leaflet"
_DEFAULT_CENTER = (39.8283, -98.5795)  # continental US — used when the incident has no ICP coordinates yet
_DEFAULT_ZOOM = 5


def _map_html(center_lat: float, center_lon: float, zoom: int) -> str:
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
  .team-marker-label::before {{
    display: none;
  }}
</style>
</head>
<body>
<div id="map"></div>
<script src="leaflet.js"></script>
<script>
  var map = L.map('map').setView([{center_lat}, {center_lon}], {zoom});
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
  }}).addTo(map);
  var markers = {{}};
  function upsertMarker(teamId, name, lat, lon) {{
    var key = String(teamId);
    if (markers[key]) {{
      markers[key].setLatLng([lat, lon]);
    }} else {{
      markers[key] = L.marker([lat, lon]).addTo(map);
    }}
    markers[key].bindPopup(name);
    markers[key].bindTooltip(name, {{
      permanent: true,
      direction: 'top',
      offset: [0, -10],
      opacity: 1,
      className: 'team-marker-label'
    }});
  }}
  function removeMarker(teamId) {{
    var key = String(teamId);
    if (markers[key]) {{
      map.removeLayer(markers[key]);
      delete markers[key];
    }}
  }}
</script>
</body>
</html>"""


class TeamLocationMapPanel(QWidget):
    """Standalone panel: tile basemap + pan/zoom + one marker per tracked team."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._known_located_teams: set[int] = set()
        self._ready = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        incident = incident_cache.active_incident() or {}
        center_lat = incident.get("latitude") or _DEFAULT_CENTER[0]
        center_lon = incident.get("longitude") or _DEFAULT_CENTER[1]

        self._view = QWebEngineView(self)
        # The map HTML is loaded from a local file:// base URL (the vendored
        # Leaflet assets), and QtWebEngine blocks "local content" from
        # fetching remote (https://) subresources by default — silently, an
        # <img> tile just sits at complete=true/naturalWidth=0 with no error
        # surfaced to page JS. The OSM tile layer is a remote https fetch
        # from that local-origin page, so this must be explicitly enabled.
        self._view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        self._view.loadFinished.connect(self._on_load_finished)
        layout.addWidget(self._view)

        html = _map_html(center_lat, center_lon, _DEFAULT_ZOOM)
        base_url = QUrl(_ASSETS_DIR.as_uri() + "/")
        self._view.setHtml(html, base_url)

        incident_cache.changed.connect(self._on_cache_changed)
        self.destroyed.connect(lambda _=None: self._disconnect())

    def _disconnect(self) -> None:
        try:
            incident_cache.changed.disconnect(self._on_cache_changed)
        except Exception:
            pass

    def _on_load_finished(self, ok: bool) -> None:
        if not ok:
            logger.warning("TeamLocationMapPanel: map HTML failed to load")
            return
        self._ready = True
        for doc in incident_cache.get_all("teams"):
            self._apply_team_doc(doc)

    def _on_cache_changed(self, collection: str, op: str, doc_id: str) -> None:
        if collection != "teams" or not self._ready:
            return
        # A hard-deleted team can't be recovered from the cache to resolve
        # its int_id for marker removal, but TEAMS docs are soft-deleted by
        # default (BaseRepository) — the realistic delete path lands here as
        # an "updated" doc with deleted=True, which _apply_team_doc handles.
        if op == "deleted":
            return
        doc = incident_cache.get("teams", doc_id)
        if doc is not None:
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
                self._run_js(f"removeMarker({team_id});")
            return
        name = doc.get("name") or f"Team {team_id}"
        self._known_located_teams.add(team_id)
        self._run_js(f"upsertMarker({team_id}, {json.dumps(name)}, {lat}, {lon});")

    def _run_js(self, script: str) -> None:
        page = self._view.page()
        if page is not None:
            page.runJavaScript(script)
