import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { ArrowLeft } from "lucide-react";
import { useSession } from "../../auth/SessionContext";
import type { SpatialFeature } from "../../api/types";
import { parseWkt } from "./wkt";
import { useArchiveSpatialFeature, useSpatialFeatures } from "./hooks";
import "./incidentMap.css";

type RibbonTab = "home" | "incident" | "file" | "layers" | "view";
type BottomTab = "feature-table" | "search-results" | "coordinates" | "timeline" | "downloads" | "log";
type Basemap = "osm" | "topo";

const BASEMAPS: Record<Basemap, { label: string; url: string; attribution: string }> = {
  osm: {
    label: "OpenStreetMap",
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  },
  topo: {
    label: "OpenTopoMap",
    url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
    attribution: '&copy; OpenStreetMap contributors, SRTM | &copy; <a href="https://opentopomap.org">OpenTopoMap</a>',
  },
};

const DEFAULT_CENTER: [number, number] = [39.8283, -98.5795]; // CONUS fallback until features/incident load
const DEFAULT_ZOOM = 4;

function formatDms(value: number, isLat: boolean): string {
  const hemisphere = isLat ? (value >= 0 ? "N" : "S") : value >= 0 ? "E" : "W";
  const abs = Math.abs(value);
  const degrees = Math.floor(abs);
  const minutesFull = (abs - degrees) * 60;
  const minutes = Math.floor(minutesFull);
  const seconds = (minutesFull - minutes) * 60;
  return `${degrees}°${minutes}'${seconds.toFixed(1)}"${hemisphere}`;
}

function timestamp(): string {
  return new Date().toLocaleTimeString("en-US", { hour12: false });
}

export default function IncidentMapPage() {
  const navigate = useNavigate();
  const { incidentId } = useSession();
  const { data: features = [], isLoading } = useSpatialFeatures(incidentId!);
  const archiveFeature = useArchiveSpatialFeature(incidentId!);

  const [ribbonTab, setRibbonTab] = useState<RibbonTab>("home");
  const [bottomTab, setBottomTab] = useState<BottomTab>("feature-table");
  const [bottomCollapsed, setBottomCollapsed] = useState(false);
  const [selectedFeatureId, setSelectedFeatureId] = useState<number | null>(null);
  const [basemap, setBasemap] = useState<Basemap>("osm");
  // Visual parity with desktop's Pan/Select tool buttons only — dragging the
  // map always pans and clicking a feature always selects it either way, so
  // this toggle doesn't change map behavior yet.
  const [navTool, setNavTool] = useState<"pan" | "select">("pan");
  const [searchText, setSearchText] = useState("");
  const [searchResults, setSearchResults] = useState<SpatialFeature[]>([]);
  const [coordLat, setCoordLat] = useState("");
  const [coordLon, setCoordLon] = useState("");
  const [goToReadout, setGoToReadout] = useState<string | null>(null);
  const [cursor, setCursor] = useState<{ lat: number; lon: number } | null>(null);
  const [zoom, setZoom] = useState(DEFAULT_ZOOM);
  const [log, setLog] = useState<string[]>([]);

  const appendLog = (message: string) => setLog((prev) => [...prev, `[${timestamp()}] ${message}`]);

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);
  const featureLayerGroupRef = useRef<L.LayerGroup | null>(null);
  const layersByFeatureIdRef = useRef<Map<number, L.Path>>(new Map());
  const extentHistoryRef = useRef<{ stack: L.LatLngBounds[]; index: number }>({ stack: [], index: -1 });

  const selectedFeature = useMemo(
    () => features.find((f) => f.id === selectedFeatureId) ?? null,
    [features, selectedFeatureId]
  );

  // -- Map init (once) ----------------------------------------------------
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;
    const map = L.map(mapContainerRef.current, { center: DEFAULT_CENTER, zoom: DEFAULT_ZOOM });
    mapRef.current = map;
    const tiles = L.tileLayer(BASEMAPS.osm.url, { attribution: BASEMAPS.osm.attribution, maxZoom: 19 });
    tiles.addTo(map);
    tileLayerRef.current = tiles;
    featureLayerGroupRef.current = L.layerGroup().addTo(map);

    map.on("mousemove", (e: L.LeafletMouseEvent) => setCursor({ lat: e.latlng.lat, lon: e.latlng.lng }));
    map.on("zoomend", () => setZoom(map.getZoom()));

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // -- Basemap switch -------------------------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (tileLayerRef.current) map.removeLayer(tileLayerRef.current);
    const config = BASEMAPS[basemap];
    const tiles = L.tileLayer(config.url, { attribution: config.attribution, maxZoom: 19 });
    tiles.addTo(map);
    tileLayerRef.current = tiles;
  }, [basemap]);

  // -- Record an extent (for Prev/Next) before moving the view -----------
  const pushExtent = () => {
    const map = mapRef.current;
    if (!map) return;
    const history = extentHistoryRef.current;
    history.stack = history.stack.slice(0, history.index + 1);
    history.stack.push(map.getBounds());
    history.index = history.stack.length - 1;
  };

  const goToPrevExtent = () => {
    const map = mapRef.current;
    const history = extentHistoryRef.current;
    if (!map || history.index <= 0) return;
    history.index -= 1;
    map.fitBounds(history.stack[history.index]);
  };

  const goToNextExtent = () => {
    const map = mapRef.current;
    const history = extentHistoryRef.current;
    if (!map || history.index >= history.stack.length - 1) return;
    history.index += 1;
    map.fitBounds(history.stack[history.index]);
  };

  // -- Render features on the map whenever they change --------------------
  useEffect(() => {
    const map = mapRef.current;
    const group = featureLayerGroupRef.current;
    if (!map || !group) return;
    group.clearLayers();
    layersByFeatureIdRef.current.clear();

    for (const feature of features) {
      const geometry = parseWkt(feature.geometry_wkt);
      if (!geometry) continue;
      let layer: L.Path | null = null;
      if (geometry.type === "Point") {
        layer = L.circleMarker(geometry.latlngs, {
          radius: 7,
          color: "#1d7d7d",
          weight: 2,
          fillColor: "#1d7d7d",
          fillOpacity: 0.85,
          className: "im-feature-point",
        });
      } else if (geometry.type === "LineString") {
        layer = L.polyline(geometry.latlngs, { color: "#1d7d7d", weight: 3 });
      } else if (geometry.type === "Polygon") {
        layer = L.polygon(geometry.latlngs, { color: "#1d7d7d", weight: 2, fillOpacity: 0.2 });
      }
      if (!layer) continue;
      layer.bindTooltip(feature.label || feature.feature_type);
      layer.on("click", () => {
        setSelectedFeatureId(feature.id);
        appendLog(`Selected: ${feature.label} (${feature.feature_type})`);
      });
      layer.addTo(group);
      layersByFeatureIdRef.current.set(feature.id, layer);
    }
  }, [features]);

  // -- Highlight the selected feature's own layer --------------------------
  useEffect(() => {
    for (const [featureId, layer] of layersByFeatureIdRef.current) {
      const isSelected = featureId === selectedFeatureId;
      if (layer instanceof L.CircleMarker) {
        layer.setStyle({ color: isSelected ? "#5b9bd5" : "#1d7d7d", weight: isSelected ? 3 : 2 });
      } else {
        layer.setStyle({ color: isSelected ? "#5b9bd5" : "#1d7d7d", weight: isSelected ? 4 : 3 });
      }
    }
  }, [selectedFeatureId]);

  // -- Feature-table / search-result navigation ---------------------------
  const flyToFeature = (feature: SpatialFeature) => {
    const map = mapRef.current;
    if (!map) return;
    pushExtent();
    if (feature.centroid_lat != null && feature.centroid_lon != null) {
      map.setView([feature.centroid_lat, feature.centroid_lon], Math.max(map.getZoom(), 15));
    }
    setSelectedFeatureId(feature.id);
  };

  const onRunSearch = () => {
    const query = searchText.trim().toLowerCase();
    if (!query) {
      setSearchResults([]);
      return;
    }
    const matches = features.filter((f) => f.label.toLowerCase().includes(query));
    setSearchResults(matches);
    setBottomCollapsed(false);
    setBottomTab("search-results");
    appendLog(`Searched "${searchText}" — ${matches.length} match(es).`);
  };

  // -- Operational View: zoom to the incident's loaded features -----------
  const onZoomToIncident = () => {
    const map = mapRef.current;
    if (!map) return;
    const points: [number, number][] = features
      .filter((f) => f.centroid_lat != null && f.centroid_lon != null)
      .map((f) => [f.centroid_lat as number, f.centroid_lon as number]);
    if (points.length === 0) {
      appendLog("No spatial features loaded to zoom to yet.");
      return;
    }
    pushExtent();
    map.fitBounds(L.latLngBounds(points), { padding: [40, 40] });
  };

  const onZoomToSelection = () => {
    const map = mapRef.current;
    if (!map || !selectedFeature) return;
    pushExtent();
    const { bbox_min_lat, bbox_min_lon, bbox_max_lat, bbox_max_lon, centroid_lat, centroid_lon } = selectedFeature;
    if (bbox_min_lat != null && bbox_min_lon != null && bbox_max_lat != null && bbox_max_lon != null) {
      map.fitBounds([[bbox_min_lat, bbox_min_lon], [bbox_max_lat, bbox_max_lon]], { padding: [40, 40] });
    } else if (centroid_lat != null && centroid_lon != null) {
      map.setView([centroid_lat, centroid_lon], Math.max(map.getZoom(), 15));
    }
  };

  const onGoToMyLocation = () => {
    if (!navigator.geolocation) {
      appendLog("Device location isn't available in this browser.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const map = mapRef.current;
        if (!map) return;
        pushExtent();
        map.setView([position.coords.latitude, position.coords.longitude], 15);
        appendLog("Centered on device location.");
      },
      () => appendLog("Device location unavailable or permission denied; use Coordinate Entry."),
    );
  };

  const onGoToCoordinates = () => {
    const lat = Number(coordLat);
    const lon = Number(coordLon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
    const map = mapRef.current;
    if (map) {
      pushExtent();
      map.setView([lat, lon], Math.max(map.getZoom(), 14));
    }
    setGoToReadout(`${formatDms(lat, true)}  ${formatDms(lon, false)}`);
    appendLog(`Went to ${lat.toFixed(6)}, ${lon.toFixed(6)}.`);
  };

  const onDeleteSelected = () => {
    if (!selectedFeature) return;
    if (!window.confirm(`Delete "${selectedFeature.label}"?`)) return;
    archiveFeature.mutate(selectedFeature.id, {
      onSuccess: () => {
        appendLog(`Deleted: ${selectedFeature.label}`);
        setSelectedFeatureId(null);
      },
    });
  };

  const goBack = () => {
    if (window.history.length > 1) navigate(-1);
    else navigate("/");
  };

  return (
    <div className="im-page">
      <header className="im-topbar">
        <button type="button" className="im-back-btn" onClick={goBack}>
          <ArrowLeft size={14} /> Close
        </button>
        <div>
          <h1>Incident Map</h1>
          <div className="sub">{isLoading ? "Loading features…" : `${features.length} spatial feature(s)`}</div>
        </div>
      </header>

      <div className="im-ribbon">
        <div className="im-ribbon-tabs">
          {(["home", "incident", "file", "layers", "view"] as RibbonTab[]).map((tab) => (
            <button
              key={tab}
              type="button"
              className={"im-ribbon-tab" + (ribbonTab === tab ? " active" : "")}
              onClick={() => setRibbonTab(tab)}
            >
              {tab[0].toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        {ribbonTab === "home" && (
          <div className="im-ribbon-page active">
            <div className="im-rgroup">
              <div className="im-rgroup-buttons">
                <button className={"im-rbtn" + (navTool === "pan" ? " active" : "")} type="button" title="Dragging the map always pans" onClick={() => setNavTool("pan")}>Pan</button>
                <button className={"im-rbtn" + (navTool === "select" ? " active" : "")} type="button" title="Clicking a feature always selects it" onClick={() => setNavTool("select")}>Select</button>
                <button className="im-rbtn" type="button" title="Zoom in" onClick={() => mapRef.current?.zoomIn()}>Zoom In</button>
                <button className="im-rbtn" type="button" title="Zoom out" onClick={() => mapRef.current?.zoomOut()}>Zoom Out</button>
                <button className="im-rbtn" type="button" title="Previous extent" onClick={goToPrevExtent}>Prev</button>
                <button className="im-rbtn" type="button" title="Next extent" onClick={goToNextExtent}>Next</button>
              </div>
              <span className="im-rgroup-label">Navigation</span>
            </div>
            <div className="im-rgroup">
              <div className="im-rgroup-buttons">
                <input
                  className="im-rgroup-input"
                  placeholder="Search features…"
                  value={searchText}
                  onChange={(e) => setSearchText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && onRunSearch()}
                />
                <button className="im-rbtn" type="button" onClick={onRunSearch}>Search</button>
                <button className="im-rbtn" type="button" title="Coordinate Entry" onClick={() => { setBottomCollapsed(false); setBottomTab("coordinates"); }}>Coords</button>
                <button className="im-rbtn" type="button" title="My Location" onClick={onGoToMyLocation}>Location</button>
              </div>
              <span className="im-rgroup-label">Find / Go To</span>
            </div>
            <div className="im-rgroup">
              <div className="im-rgroup-buttons">
                <button className="im-rbtn" type="button" title="Incident Extent" onClick={onZoomToIncident}>Incident</button>
                <button className="im-rbtn" type="button" disabled title="Team locations aren't exposed to the web client yet">Teams</button>
                <button className="im-rbtn" type="button" disabled title="Task locations aren't exposed to the web client yet">Tasks</button>
              </div>
              <span className="im-rgroup-label">Operational View</span>
            </div>
            <div className="im-rgroup">
              <div className="im-rgroup-buttons">
                <button className="im-rbtn" type="button" disabled title="Coming soon">Marker</button>
                <button className="im-rbtn" type="button" disabled title="Coming soon">Hazard</button>
                <button className="im-rbtn" type="button" disabled title="Coming soon">Clue</button>
                <button className="im-rbtn" type="button" disabled title="Coming soon">Task Area</button>
              </div>
              <span className="im-rgroup-label">Quick Add <span className="im-soon">Soon</span></span>
            </div>
            <div className="im-rgroup">
              <div className="im-rgroup-buttons">
                <button className="im-rbtn" type="button" title="Clear Selection" onClick={() => setSelectedFeatureId(null)}>Clear</button>
                <button className="im-rbtn" type="button" title="Zoom to Selection" disabled={!selectedFeature} onClick={onZoomToSelection}>Zoom</button>
              </div>
              <span className="im-rgroup-label">Selection</span>
            </div>
            <div className="im-rgroup">
              <div className="im-rgroup-buttons">
                <button className="im-rbtn" type="button" disabled title="Coming soon">Measure</button>
                <select
                  className="im-rgroup-input"
                  style={{ width: 130 }}
                  value={basemap}
                  onChange={(e) => setBasemap(e.target.value as Basemap)}
                >
                  {Object.entries(BASEMAPS).map(([key, config]) => (
                    <option key={key} value={key}>{config.label}</option>
                  ))}
                </select>
                <button className="im-rbtn" type="button" disabled title="Layer management isn't available in the web client yet">Layers</button>
              </div>
              <span className="im-rgroup-label">Map Utilities</span>
            </div>
          </div>
        )}

        {ribbonTab === "incident" && (
          <div className="im-ribbon-page active">
            <div className="im-rgroup">
              <div className="im-rgroup-buttons">
                <button className="im-rbtn" type="button" disabled title="Coming soon">LZ</button>
                <button className="im-rbtn" type="button" disabled title="Coming soon">Access Pt</button>
                <button className="im-rbtn" type="button" disabled title="Coming soon">Roadblock</button>
                <button className="im-rbtn" type="button" disabled title="Coming soon">Medical</button>
                <button className="im-rbtn" type="button" disabled title="Coming soon">Comms Site</button>
              </div>
              <span className="im-rgroup-label">Operational Points <span className="im-soon">Soon</span></span>
            </div>
            <div className="im-rgroup">
              <div className="im-rgroup-buttons">
                <button className="im-rbtn" type="button" disabled title="Coming soon">Containment</button>
                <button className="im-rbtn" type="button" disabled title="Coming soon">Route</button>
                <button className="im-rbtn" type="button" disabled title="Coming soon">Task Route</button>
              </div>
              <span className="im-rgroup-label">Operational Lines <span className="im-soon">Soon</span></span>
            </div>
            <div className="im-rgroup">
              <div className="im-rgroup-buttons">
                <button className="im-rbtn" type="button" disabled title="Coming soon">Task Area</button>
                <button className="im-rbtn" type="button" disabled title="Coming soon">Assignment</button>
              </div>
              <span className="im-rgroup-label">Operational Areas <span className="im-soon">Soon</span></span>
            </div>
            <div className="im-rgroup">
              <div className="im-rgroup-buttons">
                <button className="im-rbtn" type="button" disabled title="Coming soon">Point</button>
                <button className="im-rbtn" type="button" disabled title="Coming soon">Line</button>
                <button className="im-rbtn" type="button" disabled title="Coming soon">Polygon</button>
                <button className="im-rbtn" type="button" disabled title="Coming soon">Rectangle</button>
              </div>
              <span className="im-rgroup-label">Draw <span className="im-soon">Soon</span></span>
            </div>
            <div className="im-rgroup">
              <div className="im-rgroup-buttons">
                <button className="im-rbtn" type="button" disabled title="Coming soon">Vertices</button>
                <button className="im-rbtn" type="button" disabled title="Coming soon">Move</button>
                <button className="im-rbtn" type="button" title="Delete selected feature" disabled={!selectedFeature} onClick={onDeleteSelected}>Delete</button>
                <button className="im-rbtn" type="button" disabled title="Coming soon">Buffer…</button>
              </div>
              <span className="im-rgroup-label">Edit</span>
            </div>
            <div className="im-rgroup">
              <div className="im-rgroup-buttons">
                <button className="im-rbtn" type="button" disabled title="Coming soon">Search Grid</button>
                <button className="im-rbtn" type="button" disabled title="Coming soon">Search Pattern</button>
              </div>
              <span className="im-rgroup-label">Search Generators <span className="im-soon">Soon</span></span>
            </div>
            <div className="im-rgroup">
              <div className="im-rgroup-buttons">
                <button className="im-rbtn" type="button" disabled title="Coming soon">Convert To…</button>
              </div>
              <span className="im-rgroup-label">Convert <span className="im-soon">Soon</span></span>
            </div>
          </div>
        )}

        {(["file", "layers", "view"] as RibbonTab[]).map((tab) => (
          ribbonTab === tab && (
            <div key={tab} className="im-ribbon-page active">
              <div className="im-rgroup">
                <div className="im-rgroup-buttons">
                  <button className="im-rbtn" type="button" disabled>Coming soon</button>
                </div>
                <span className="im-rgroup-label">{tab[0].toUpperCase() + tab.slice(1)}</span>
              </div>
            </div>
          )
        ))}
      </div>

      {selectedFeature && (
        <div className="im-contextual-strip">
          <span>Selected: {selectedFeature.label} ({selectedFeature.feature_type})</span>
          <span className="spacer" />
          <button className="im-rbtn" type="button" onClick={() => { setBottomCollapsed(false); setBottomTab("feature-table"); }}>Open Details</button>
          <button className="im-rbtn" type="button" disabled title="Coming soon">Edit Vertices</button>
          <button className="im-rbtn" type="button" disabled title="Coming soon">Add Buffer</button>
          <button className="im-rbtn" type="button" onClick={onDeleteSelected}>Delete</button>
        </div>
      )}

      <div className="im-canvas-area">
        <div ref={mapContainerRef} />
      </div>

      <div className="im-bottom-panel">
        <div className="im-bottom-tabs">
          {([
            ["feature-table", "Feature Table"],
            ["search-results", "Search Results"],
            ["coordinates", "Coordinates"],
            ["timeline", "Timeline"],
            ["downloads", "Downloads"],
            ["log", "Log"],
          ] as [BottomTab, string][]).map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={"im-bottom-tab" + (bottomTab === key ? " active" : "")}
              onClick={() => { setBottomCollapsed(false); setBottomTab(key); }}
            >
              {label}
            </button>
          ))}
          <button className="im-bottom-collapse" type="button" onClick={() => setBottomCollapsed((c) => !c)}>
            {bottomCollapsed ? "▲ Expand" : "▼ Collapse"}
          </button>
        </div>

        {!bottomCollapsed && (
          <div className="im-bottom-content">
            {bottomTab === "feature-table" && (
              features.length === 0 ? (
                <p className="im-empty">No spatial features for this incident yet.</p>
              ) : (
                <table className="im-table">
                  <thead><tr><th>ID</th><th>Type</th><th>Label</th><th>Layer</th></tr></thead>
                  <tbody>
                    {features.map((f) => (
                      <tr key={f.id} className={f.id === selectedFeatureId ? "selected" : ""} onClick={() => flyToFeature(f)}>
                        <td>{f.id}</td>
                        <td>{f.feature_type}</td>
                        <td>{f.label}</td>
                        <td>{f.layer_key}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            )}

            {bottomTab === "search-results" && (
              searchResults.length === 0 ? (
                <p className="im-empty">No search run yet — try Find / Go To on the Home tab.</p>
              ) : (
                <table className="im-table">
                  <tbody>
                    {searchResults.map((f) => (
                      <tr key={f.id} className={f.id === selectedFeatureId ? "selected" : ""} onClick={() => flyToFeature(f)}>
                        <td>{f.label}</td>
                        <td>{f.feature_type}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            )}

            {bottomTab === "coordinates" && (
              <div>
                <div className="im-coord-form">
                  <div className="field"><label>Latitude</label><input value={coordLat} onChange={(e) => setCoordLat(e.target.value)} placeholder="41.223000" /></div>
                  <div className="field"><label>Longitude</label><input value={coordLon} onChange={(e) => setCoordLon(e.target.value)} placeholder="-111.812000" /></div>
                  <button className="im-rbtn" type="button" onClick={onGoToCoordinates}>Go To</button>
                </div>
                <p className="im-coord-readout">
                  {goToReadout ? `DMS: ${goToReadout}` : "DMS readout appears here after Go To."}
                  <br />
                  UTM / MGRS conversions aren't available in the web client yet.
                </p>
              </div>
            )}

            {bottomTab === "timeline" && <p className="im-empty">Timeline — coming soon.</p>}
            {bottomTab === "downloads" && <p className="im-empty">Downloads — coming soon.</p>}

            {bottomTab === "log" && (
              log.length === 0 ? (
                <p className="im-empty">No activity logged yet this session.</p>
              ) : (
                log.slice().reverse().map((line, i) => <p key={i} className="im-log-line">{line}</p>)
              )
            )}
          </div>
        )}
      </div>

      <div className="im-statusbar">
        <span>Cursor: {cursor ? `${cursor.lat.toFixed(5)}, ${cursor.lon.toFixed(5)}` : "-"}</span>
        <span>Zoom: {zoom}</span>
        <span className="sep" />
        <span>Online</span>
      </div>
    </div>
  );
}
