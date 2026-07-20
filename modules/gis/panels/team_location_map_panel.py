"""Team-location map panel — GIS module Phase 1 (see modules/gis/DEVELOPER_NOTE.md
and tracking_plan.md in ICS-Mobile-App for the full design).

Renders a Leaflet basemap with basic navigation controls and one marker per
team, sourced from mobile GPS pings (see
data/db/sarapp_db/api/routers/mobile_location.py on the server side). No
drawing tools, no spatial_features wiring, no breadcrumb trail — only each
team's last-known position. This panel is meant as the permanent foundation
later GIS-module phases extend (assignment-area drawing, spatial-feature
layers), not a throwaway MVP widget.

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

from PySide6.QtCore import QObject, QSettings, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from utils import incident_context
from utils.incident_cache import incident_cache
from utils.table_view_styles import apply_statusboard_table_behavior

logger = logging.getLogger(__name__)

_ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "leaflet"
_DEFAULT_CENTER = (39.8283, -98.5795)  # continental US — used when the incident has no ICP coordinates yet
_DEFAULT_ZOOM = 5
_DEFAULT_BASEMAP = "osm"
_VIEW_SETTINGS = QSettings("SARApp", "GIS")
_BASEMAPS: dict[str, dict[str, Any]] = {
    "osm": {
        "label": "OpenStreetMap",
        "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "options": {
            "maxZoom": 19,
            "attribution": "&copy; OpenStreetMap contributors",
        },
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
  .team-marker-label::before {{
    display: none;
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
    if (basemapLayer) {{
      map.removeLayer(basemapLayer);
    }}
    basemapLayer = L.tileLayer(cfg.url, cfg.options);
    basemapLayer.addTo(map);
    currentBasemapKey = key in basemapConfigs ? key : 'osm';
  }}
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
  function zoomInMap() {{
    map.zoomIn();
  }}
  function zoomOutMap() {{
    map.zoomOut();
  }}
  function centerMap(lat, lon, zoom) {{
    if (typeof zoom === 'number') {{
      map.setView([lat, lon], zoom);
      return;
    }}
    map.setView([lat, lon], map.getZoom());
  }}
  function fitToMarkers() {{
    var coords = [];
    Object.keys(markers).forEach(function(key) {{
      coords.push(markers[key].getLatLng());
    }});
    if (!coords.length) {{
      return false;
    }}
    map.fitBounds(L.latLngBounds(coords), {{ padding: [24, 24], maxZoom: 14 }});
    return true;
  }}
  function setBasemap(key) {{
    applyBasemap(key);
    return currentBasemapKey;
  }}
  function getMapState() {{
    var center = map.getCenter();
    return {{
      center_lat: center.lat,
      center_lon: center.lng,
      zoom: map.getZoom(),
      basemap_key: currentBasemapKey
    }};
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


class TeamMapInspectorPanel(QWidget):
    """Read-focused inspector for the currently selected team marker."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_team_id: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        title = QLabel("Inspector", self)
        title.setStyleSheet("font-weight: 700;")
        layout.addWidget(title)

        self._empty_label = QLabel("Select a team marker to inspect connected records.", self)
        self._empty_label.setWordWrap(True)
        layout.addWidget(self._empty_label)

        identity_group = QGroupBox("Identity", self)
        identity_form = QFormLayout(identity_group)
        self._team_name_value = QLabel("-", self)
        self._team_id_value = QLabel("-", self)
        self._team_type_value = QLabel("-", self)
        self._leader_value = QLabel("-", self)
        identity_form.addRow("Team", self._team_name_value)
        identity_form.addRow("Team ID", self._team_id_value)
        identity_form.addRow("Type", self._team_type_value)
        identity_form.addRow("Leader", self._leader_value)
        layout.addWidget(identity_group)

        status_group = QGroupBox("Status", self)
        status_form = QFormLayout(status_group)
        self._status_value = QLabel("-", self)
        self._assignment_value = QLabel("-", self)
        self._last_update_value = QLabel("-", self)
        status_form.addRow("Status", self._status_value)
        status_form.addRow("Assignment", self._assignment_value)
        status_form.addRow("Last Update", self._last_update_value)
        layout.addWidget(status_group)

        location_group = QGroupBox("Location", self)
        location_form = QFormLayout(location_group)
        self._coordinates_value = QLabel("-", self)
        self._text_location_value = QLabel("-", self)
        location_form.addRow("Coordinates", self._coordinates_value)
        location_form.addRow("Reported Location", self._text_location_value)
        layout.addWidget(location_group)

        connected_group = QGroupBox("Connected Records", self)
        connected_layout = QVBoxLayout(connected_group)
        self._connections_table = QTableWidget(0, 4, self)
        self._connections_table.setHorizontalHeaderLabels(["Type", "Record", "Title", "Status"])
        apply_statusboard_table_behavior(self._connections_table, stretch_last_section=True)
        self._connections_table.verticalHeader().setVisible(False)
        self._connections_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._connections_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        connected_layout.addWidget(self._connections_table)
        layout.addWidget(connected_group, 1)

        layout.addStretch(1)
        self._set_content_visible(False)

    def set_team(self, team_id: int | None) -> None:
        self._selected_team_id = team_id
        self.refresh()

    def refresh(self) -> None:
        if self._selected_team_id is None:
            self._clear()
            return
        team = self._team_doc(self._selected_team_id)
        if not team:
            self._clear()
            return

        self._empty_label.hide()
        self._set_content_visible(True)
        self._team_name_value.setText(str(team.get("name") or f"Team {self._selected_team_id}"))
        self._team_id_value.setText(str(team.get("int_id") or self._selected_team_id))
        self._team_type_value.setText(str(team.get("team_type") or "-"))
        self._leader_value.setText(self._leader_name(team))
        self._status_value.setText(str(team.get("status") or "available"))
        self._assignment_value.setText(self._assignment_text(team))
        self._last_update_value.setText(str(team.get("current_location_updated_at") or team.get("status_updated") or "-"))
        lat = team.get("current_location_lat")
        lon = team.get("current_location_lon")
        if lat is None or lon is None:
            self._coordinates_value.setText("-")
        else:
            self._coordinates_value.setText(f"{lat:.5f}, {lon:.5f}")
        self._text_location_value.setText(str(team.get("location") or "-"))

        connections = self._connected_records(team)
        self._connections_table.setRowCount(len(connections))
        for row, item in enumerate(connections):
            self._connections_table.setItem(row, 0, QTableWidgetItem(str(item.get("kind") or "")))
            self._connections_table.setItem(row, 1, QTableWidgetItem(str(item.get("record") or "")))
            self._connections_table.setItem(row, 2, QTableWidgetItem(str(item.get("title") or "")))
            self._connections_table.setItem(row, 3, QTableWidgetItem(str(item.get("status") or "")))

    def _clear(self) -> None:
        self._selected_team_id = None
        self._empty_label.show()
        self._set_content_visible(False)
        for label in (
            self._team_name_value,
            self._team_id_value,
            self._team_type_value,
            self._leader_value,
            self._status_value,
            self._assignment_value,
            self._last_update_value,
            self._coordinates_value,
            self._text_location_value,
        ):
            label.setText("-")
        self._connections_table.setRowCount(0)

    def _set_content_visible(self, visible: bool) -> None:
        for widget in self.findChildren(QGroupBox):
            widget.setVisible(visible)

    def _team_doc(self, team_id: int) -> dict[str, Any] | None:
        for doc in incident_cache.get_all("teams"):
            if doc.get("int_id") == team_id:
                return doc
        return None

    def _leader_name(self, team: dict[str, Any]) -> str:
        leader_name = str(team.get("leader_name") or "").strip()
        if leader_name:
            return leader_name
        raw_leader = team.get("leader_person_record") or team.get("leader_personnel_id") or team.get("team_leader")
        try:
            leader_id = int(raw_leader)
        except (TypeError, ValueError):
            return "-"
        for person in incident_cache.get_all("incident_personnel"):
            person_record = person.get("person_record") or person.get("master_id")
            try:
                if int(person_record) == leader_id:
                    return str(
                        person.get("name")
                        or (((person.get("first_name") or "") + " " + (person.get("last_name") or "")).strip())
                        or f"#{leader_id}"
                    )
            except (TypeError, ValueError):
                continue
        return f"#{leader_id}"

    def _assignment_text(self, team: dict[str, Any]) -> str:
        tasks = self._connected_tasks(team)
        if not tasks:
            return "-"
        task = tasks[0]
        number = str(task.get("task_id") or task.get("int_id") or "")
        title = str(task.get("title") or "")
        return f"{number} - {title}".strip(" -")

    def _connected_tasks(self, team: dict[str, Any]) -> list[dict[str, Any]]:
        team_int_id = team.get("int_id")
        team_ref = team.get("team_id") or str(team_int_id)
        current_task_ref = team.get("current_task_id")
        tasks: list[dict[str, Any]] = []
        seen: set[Any] = set()
        for task in incident_cache.get_all("tasks"):
            match = False
            if current_task_ref is not None and current_task_ref in (
                task.get("int_id"),
                task.get("task_id"),
            ):
                match = True
            active_ids = task.get("active_team_ids") or []
            if team_int_id in active_ids or team_ref in active_ids:
                match = True
            for tt in task.get("task_teams") or task.get("assigned_teams") or []:
                if tt.get("team_id") in (team_int_id, team_ref):
                    match = True
                    break
            if match:
                key = task.get("_id") or task.get("int_id") or task.get("task_id")
                if key not in seen:
                    seen.add(key)
                    tasks.append(task)
        tasks.sort(key=lambda item: item.get("int_id") or 0)
        return tasks

    def _connected_records(self, team: dict[str, Any]) -> list[dict[str, str]]:
        connected: list[dict[str, str]] = []
        tasks = self._connected_tasks(team)
        task_refs = {
            str(ref)
            for task in tasks
            for ref in (task.get("int_id"), task.get("task_id"))
            if ref not in (None, "")
        }

        for task in tasks:
            connected.append({
                "kind": "Task",
                "record": str(task.get("task_id") or task.get("int_id") or ""),
                "title": str(task.get("title") or ""),
                "status": str(task.get("status") or ""),
            })

        lead_ids_from_items: set[str] = set()
        team_name = str(team.get("name") or "").strip().lower()
        leader_name = self._leader_name(team).strip().lower()

        for item in incident_cache.get_all("intel_items"):
            linked_task_ids = {str(v) for v in (item.get("linked_task_ids") or []) if v not in (None, "")}
            linked_team_ids = {str(v) for v in (item.get("linked_team_ids") or []) if v not in (None, "")}
            team_hit = str(team.get("int_id")) in linked_team_ids
            task_hit = bool(task_refs.intersection(linked_task_ids))
            if not team_hit and not task_hit:
                continue
            connected.append({
                "kind": "Intel",
                "record": str(item.get("id") or ""),
                "title": f"{item.get('item_type') or 'Item'}: {item.get('title') or ''}".strip(),
                "status": str(item.get("status") or ""),
            })
            source_lead_id = item.get("source_lead_id")
            if source_lead_id not in (None, ""):
                lead_ids_from_items.add(str(source_lead_id))

        for lead in incident_cache.get_all("intel_leads"):
            lead_id = str(lead.get("id") or "")
            assigned_to = str(lead.get("assigned_to") or "").strip().lower()
            if (
                lead_id in lead_ids_from_items
                or (assigned_to and assigned_to in {team_name, leader_name})
            ):
                connected.append({
                    "kind": "Lead",
                    "record": f"L-{int(lead.get('lead_number') or 0):03d}" if lead.get("lead_number") else lead_id,
                    "title": str(lead.get("title") or ""),
                    "status": str(lead.get("status") or ""),
                })

        return connected


class TeamLocationMapPanel(QWidget):
    """First-pass GIS shell: top toolbar + map canvas + tracked team markers."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._known_located_teams: set[int] = set()
        self._ready = False
        self._incident_id = str(incident_context.get_active_incident_id() or "default")
        self._persist_timer = QTimer(self)
        self._persist_timer.setInterval(3000)
        self._persist_timer.timeout.connect(self._persist_map_state)
        self._bridge = _MapSelectionBridge(self)
        self._bridge.teamSelected.connect(self._on_team_selected)
        self._web_channel = QWebChannel(self)
        self._web_channel.registerObject("mapBridge", self._bridge)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        incident = incident_cache.active_incident() or {}
        self._incident_center = (
            float(incident.get("latitude") or _DEFAULT_CENTER[0]),
            float(incident.get("longitude") or _DEFAULT_CENTER[1]),
        )
        saved_view = self._load_saved_view()
        center_lat = saved_view.get("center_lat", self._incident_center[0])
        center_lon = saved_view.get("center_lon", self._incident_center[1])
        zoom = saved_view.get("zoom", _DEFAULT_ZOOM)
        basemap_key = saved_view.get("basemap_key", _DEFAULT_BASEMAP)

        controls = QHBoxLayout()
        controls.setContentsMargins(8, 8, 8, 0)

        map_label = QLabel("Map", self)
        controls.addWidget(map_label)

        self._basemap_combo = QComboBox(self)
        for key, config in _BASEMAPS.items():
            self._basemap_combo.addItem(str(config["label"]), key)
        selected_index = self._basemap_combo.findData(basemap_key)
        if selected_index >= 0:
            self._basemap_combo.setCurrentIndex(selected_index)
        self._basemap_combo.currentIndexChanged.connect(self._on_basemap_changed)
        controls.addWidget(self._basemap_combo)

        zoom_in_button = QPushButton("+", self)
        zoom_in_button.setFixedWidth(36)
        zoom_in_button.clicked.connect(lambda: self._run_js("zoomInMap();"))
        controls.addWidget(zoom_in_button)

        zoom_out_button = QPushButton("-", self)
        zoom_out_button.setFixedWidth(36)
        zoom_out_button.clicked.connect(lambda: self._run_js("zoomOutMap();"))
        controls.addWidget(zoom_out_button)

        center_button = QPushButton("Center Incident", self)
        center_button.clicked.connect(self._center_on_incident)
        controls.addWidget(center_button)

        fit_visible_button = QPushButton("Fit Visible", self)
        fit_visible_button.clicked.connect(self._fit_visible)
        controls.addWidget(fit_visible_button)
        controls.addStretch(1)
        layout.addLayout(controls)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)

        map_shell = QWidget(self)
        map_shell_layout = QVBoxLayout(map_shell)
        map_shell_layout.setContentsMargins(0, 0, 0, 0)

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
        self._view.page().setWebChannel(self._web_channel)
        self._view.loadFinished.connect(self._on_load_finished)
        map_shell_layout.addWidget(self._view)

        self._inspector = TeamMapInspectorPanel(self)

        splitter.addWidget(map_shell)
        splitter.addWidget(self._inspector)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([900, 320])
        layout.addWidget(splitter, 1)

        html = _map_html(center_lat, center_lon, zoom, basemap_key)
        base_url = QUrl(_ASSETS_DIR.as_uri() + "/")
        self._view.setHtml(html, base_url)

        incident_cache.changed.connect(self._on_cache_changed)
        self.destroyed.connect(lambda _=None: self._disconnect())

    def _disconnect(self) -> None:
        self._persist_map_state()
        self._persist_timer.stop()
        try:
            incident_cache.changed.disconnect(self._on_cache_changed)
        except Exception:
            pass

    def _on_load_finished(self, ok: bool) -> None:
        if not ok:
            logger.warning("TeamLocationMapPanel: map HTML failed to load")
            return
        self._ready = True
        self._persist_timer.start()
        for doc in incident_cache.get_all("teams"):
            self._apply_team_doc(doc)

    def _on_cache_changed(self, collection: str, op: str, doc_id: str) -> None:
        if collection != "teams" or not self._ready:
            if collection in {"tasks", "intel_items", "intel_leads", "incident_personnel"}:
                self._inspector.refresh()
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
        self._inspector.refresh()

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

    def _on_basemap_changed(self) -> None:
        key = self._basemap_combo.currentData()
        if not self._ready or not key:
            return
        self._run_js(f"setBasemap({json.dumps(str(key))});", callback=lambda _=None: self._persist_map_state())

    def _center_on_incident(self) -> None:
        lat, lon = self._incident_center
        self._run_js(f"centerMap({lat}, {lon}, {_DEFAULT_ZOOM});", callback=lambda _=None: self._persist_map_state())

    def _fit_visible(self) -> None:
        self._run_js("fitToMarkers();", callback=lambda _=None: self._persist_map_state())

    def _on_team_selected(self, team_id: int) -> None:
        self._inspector.set_team(team_id)

    def _settings_prefix(self) -> str:
        return f"map_view/{self._incident_id}"

    def _load_saved_view(self) -> dict[str, Any]:
        prefix = self._settings_prefix()
        zoom_value = _VIEW_SETTINGS.value(f"{prefix}/zoom", _DEFAULT_ZOOM)
        try:
            zoom = int(zoom_value)
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
        return {
            "center_lat": center_lat,
            "center_lon": center_lon,
            "zoom": zoom,
            "basemap_key": basemap_key,
        }

    def _persist_map_state(self) -> None:
        if not self._ready:
            return
        self._run_js("getMapState();", callback=self._save_map_state)

    def _save_map_state(self, state: Any) -> None:
        if not isinstance(state, dict):
            return
        try:
            center_lat = float(state.get("center_lat"))
            center_lon = float(state.get("center_lon"))
            zoom = int(state.get("zoom"))
        except (TypeError, ValueError):
            return
        basemap_key = str(state.get("basemap_key") or _DEFAULT_BASEMAP)
        if basemap_key not in _BASEMAPS:
            basemap_key = _DEFAULT_BASEMAP
        prefix = self._settings_prefix()
        _VIEW_SETTINGS.setValue(f"{prefix}/center_lat", center_lat)
        _VIEW_SETTINGS.setValue(f"{prefix}/center_lon", center_lon)
        _VIEW_SETTINGS.setValue(f"{prefix}/zoom", zoom)
        _VIEW_SETTINGS.setValue(f"{prefix}/basemap_key", basemap_key)

    def _run_js(self, script: str, callback: Any | None = None) -> None:
        page = self._view.page()
        if page is not None:
            if callback is None:
                page.runJavaScript(script)
            else:
                page.runJavaScript(script, 0, callback)
