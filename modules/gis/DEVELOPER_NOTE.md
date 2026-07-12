# GIS Framework First Pass

## What was added
- A new `modules/gis/` package with shared spatial models for geometry types, feature types, layer definitions, spatial features, and feature links.
- Central registries for feature rules (`FeatureRegistry`) and built-in layers (`LayerRegistry`).
- Incident-scoped persistence services (`SpatialRepository`, `SpatialLinkService`) and schema bootstrap support for spatial tables.
- A dependency-light geometry utility service (`GeometryService`) to validate and normalize WKT while avoiding map/GIS dependencies.
- Module adapter stubs for operations tasks/teams plus intel, safety, and communications-owned records.
- Qt Widgets inspection UI:
  - `SpatialObjectsPanel` for feature listing
  - `FeatureInspectorPanel` for read-only details
  - `GeometrySummaryWidget` for reusable geometry summary content

## How module records should link to spatial features
1. Keep module-owned business records in their home module tables.
2. Use `SpatialRepository` and one of the GIS adapters to create a `SpatialFeature` that references:
   - `source_module`
   - `source_record_type`
   - `source_record_id`
3. Use `SpatialLinkService.attach_feature(...)` for additional related records beyond the owner.
4. Query by owner with `list_features_for_record(...)` and by related links with `list_related_features(...)`.

## Next implementation step
- Add a map-engine adapter interface (no UI renderer yet) that consumes `SpatialRepository` records and layer definitions so a future QGIS/web/other map component can be plugged in without changing data ownership or schema.

## Future Architecture Decision: Leaflet (display/editing) + Headless PyQGIS (analysis/production)

Decided direction, not just an MVP stopgap — this is the intended permanent
split of responsibilities, not "Leaflet now, replaced by QGIS later":

- **Leaflet stays the permanent map-display and editing layer.** It's the
  better-suited tool for live-streaming updates (`leaflet.realtime` fits
  the team-location-ping use case architecturally, not just adequately —
  QGIS's canvas is built for an analyst working a static/slow-changing
  dataset, not absorbing continuous live position pushes) and for
  lightweight editing (`leaflet-geoman` for assignment-area polygon
  drawing/editing). It's also web-native, so it's reusable anywhere a
  browser/WebView can go (a status-board display, potentially a future
  mobile map view) — QGIS desktop cannot run outside this app at all.
- **Headless PyQGIS (`qgis.core`, `qgis.analysis`, `processing`) handles
  spatial analysis and map production**, added once those needs actually
  materialize (viewshed/terrain analysis, buffer/intersect operations
  beyond simple point-in-polygon, and `QgsPrintLayout`/`QgsLayoutExporter`
  for professional printable briefing maps — legend/scale bar/north
  arrow/title block). All confirmed usable without any QGIS GUI; this is
  the standard, documented "headless QGIS" pattern (it's how QGIS Server
  itself works), not a workaround.
- **Full QGIS GUI embedding (`qgis.gui`, an actual `QgsMapCanvas` as a
  panel) is off the table unless a compelling future reason emerges.**
  QGIS's editing tools are genuinely more powerful than
  Leaflet/leaflet-geoman (topological snapping, precise coordinate entry,
  CAD-style constrained drawing) — but not powerful enough to justify the
  integration cost: QGIS's Python bindings are built against PyQt, not
  PySide6, and mixing the two binding systems for a live interactive
  widget (not just calling library functions) is a real, unresolved
  technical risk — possible via `shiboken6`/`sip` pointer interop, but
  fiddly and not officially supported by either project. If this is ever
  revisited, de-risk with a throwaway spike (minimal PySide6 window,
  attempt to embed a working `QgsMapCanvas`, test pan/zoom/edit signal
  handling across the binding boundary) before committing architecturally.
  Reason for embedding was evaluated and rejected on integration-risk
  grounds, not on theming/docking-consistency grounds — that concern was
  explicitly deprioritized in favor of functionality-first, so it's not
  why this was declined.
- **GPL licensing is not a blocker** for any QGIS integration (headless or
  otherwise) given this project's open-source status — no agency-exposure
  concern applies here.
- **Practical continuity**: Phase 2's point-in-polygon logic (needed for
  the team-location-tracking MVP's future auto-status-on-area-entry idea)
  should use `shapely`/`pyproj` (GEOS/PROJ underneath) rather than hand-
  rolled ray-casting math — that's the same geometry engine headless
  PyQGIS uses, so nothing built now needs rework when PyQGIS analysis is
  added later.

## Leaflet Ecosystem Reference (Phase 1 MVP and Beyond)

**Phase 1 MVP (Team Location Tracking):** Leaflet core + OpenStreetMap basemap. No plugins required for the initial implementation — pan/zoom and marker placement are built into Leaflet.

### Basemap & Tile Sources (Phase 1+)
- **leaflet-providers** — comprehensive plugin providing access to 100+ basemap providers (OSM, Stamen, ESRI, Mapbox, etc.). Recommended for Phase 1 to give users basemap choice without hard-coding one.
- **leaflet.gibs** — NASA Global Imagery Browse Service tiles; useful for satellite/aerial incident areas.
- **NOAA/NWS radar tiles** — weather/storm tracking overlay; relevant for weather-related incidents.
- **allmaps-leaflet** — historical map support; may be useful for archival/reference overlays in future phases.

### File & Data Layers (Phase 2+)
For loading shapefiles, GeoJSON, and KML from files:
- **leaflet.shapefile** — native shapefile rendering
- **leaflet.filelayer** — generic file upload & rendering (GeoJSON, KML, GPX)
- **leaflet.betterfilelayer** — enhanced file layer with better UX

### Marker Styles & Icons (Phase 1+)
- **leaflet.awesome-markers** or **leaflet.beautifymarkers** — enhanced marker appearance; recommended for Phase 1 to differentiate team markers by status/role
- **leaflet.vectormarkers** — SVG-based markers for crisp rendering at any zoom
- **leaflet.donut**, **leaflet.centermarker** — alternative marker shapes for specific use cases
- **leaflet.photo** — embed photos in markers; useful for evidence/intel callouts
- **leaflet.icon-pulse** — animated pulsing markers; good for active/tracking status indication

### Marker Direction & Movement (Phase 2+)
- **leaflet.directionmarker** or **leaflet.edgemarker** — directional arrow markers; useful for team heading/direction indicators
- **leaflet.icon-pulse** — see above; also applies to movement indicators
- **leaflet-marker-direction** — directional marker styling
- **leaflet-distance-markers** — distance callouts between points; useful for route/patrol tracking

### Real-Time & Live Updates (Phase 1, Priority)
- **leaflet.realtime** ⭐ **PRIORITY** — manages live-updating GeoJSON feeds (long-polling, WebSocket). Directly applicable to Phase 1 team-location feed updates; essential for refreshing marker positions as location pings arrive.

### Drawing & Editing (Phase 2+)
- **leaflet.draw** — full polygon/circle/line/marker drawing suite; required for Phase 2 assignment-area creation UI
- **leaflet.arc**, **leaflet.arrowcircle**, **leaflet.ellipse** — geometric shape layers; useful if finer shape control needed beyond polygon/circle
- **leaflet-corridor** — draw corridors/buffers around routes; may be useful for SAR search-area expansion UI

### Coordinates & Measurement (Phase 2+)
- **leaflet.coordinates** — display/edit coordinates in various formats (decimal, DMS, UTM)
- **leaflet.utm** — UTM grid overlay and coordinate conversion
- **leaflet.mousecoordinates** — follow-cursor coordinate display; useful for planning/reference
- **leaflet.mapcentercoord** — display center point coordinates
- **leaflet-distance-markers** — see above; distance measurement

### Geocoding & Search (Phase 2+)
- **leaflet control geocoder** — address/place name lookup; useful for ICP/facility address mapping
- **esri leaflet geocoder** — ESRI geocoding service integration
- **leaflet.autocomplete** — autocomplete geocoding suggestions
- **leaflet geosearch** (?) — alternative geocoding/search widget

### Overlays & Utilities (Phase 2+)
- **leaflet.graticule** & **leaflet.autograticule** — latitude/longitude grid overlay; useful for coordinate reference
- **leaflet.timezones** — timezone boundaries; relevant for multi-jurisdiction incidents
- **leaflet.metricgrid** — metric grid overlay alternative
- **leaflet.ismdatapicker** — imagery/satellite date picker for historical imagery access
- **leaflet.rainviewer** — weather radar overlay from RainViewer
- **windy-leaflet-plugin** — wind/weather visualization from Windy
- **leaflet.indoor** — indoor/floor-plan mapping; may be useful for building search/rescue
- **leaflet.liveupdate** — generic live-update widget (consider **leaflet.realtime** as better alternative)
- **leaflet.highlightablelayers** — selectively highlight/toggle layer visibility; useful for multi-layer incident maps

### Routing (Phase 2+)
- **leaflet.routeaddress** — address-based routing
- **OSRM (Open Source Routing Machine)** — self-hosted routing engine; useful for SAR route optimization and travel-time estimation

### Routing Note
Both leaflet.routeaddress and OSRM require a routing backend (OSM data + routing engine). For SAR operations, OSRM self-hosted is preferable over a hosted service (reliability, offline capability, no API quota limits). Consider as a later-phase add-on once team-location tracking is stable.
