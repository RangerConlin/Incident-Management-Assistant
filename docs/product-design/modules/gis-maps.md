# GIS And Maps

## Purpose

Show incident geography, team locations, operational points, drawn features, and map-based search/navigation.

GIS/Maps is the spatial layer for the incident. It supports desktop planning/coordination work and mobile field awareness.

## Users

- Command and operations staff monitoring team locations.
- Planning staff drawing operational features and sketching map overlays.
- Logistics, communications, safety, and intel staff linking places to their records.
- Field teams using mobile map awareness, team locations, coordinate search, and navigation handoff.

## Current Features

- Desktop Incident Map standalone window with ribbon, contextual strip, Leaflet map canvas, status bar, and bottom panel.
- Desktop map shows team markers from incident cache when teams have current locations.
- Desktop map supports feature indexing, feature table, local feature search, geocoder search, coordinate entry, and map centering.
- Desktop map supports operational points and operational geometry placement through feature registries/controllers.
- Desktop drawing tools support points, lines, arcs, polygons, circles, rings, rectangles, planning sketches, and stored spatial features.
- Desktop selected-feature actions include open details, duplicate, add buffer, copy coordinates, export geometry, delete/archive, and zoom to selection.
- Desktop bottom panel includes Feature Table, Search Results, Coordinates, Timeline stub, Downloads stub, and Log.
- Desktop ribbon includes Home and Incident tabs; File/Layers/View tabs currently show coming-soon placeholders.
- Desktop GIS service layer includes spatial repository, feature registry, layer registry, geometry service, adapters for teams/tasks/safety/intel/comms, and spatial feature linking.
- Mobile map shows team locations, optional current-device/my-team location, search pin, coordinate pin, basemap layers, zoom controls, fit-visible, coordinate drop mode, and navigation handoff.
- Mobile map supports team-location refresh every 30 seconds, local team search, coordinate search, geocoding, basemap preference persistence, team-layer visibility preference, copy coordinates, and external navigation app links.
- Mobile basemap choices include OpenStreetMap, OpenTopoMap, USGS Topo, USGS imagery, and USGS imagery/topo.

## Core Workflows

- Open the desktop Incident Map to view the incident area, team locations, and spatial features.
- Search by feature/address/geocoder result or use coordinate entry.
- Draw planning sketches or operational geometry and persist them as incident spatial features.
- Add buffers around selected features.
- Use feature table and bottom panel results to find, select, inspect, duplicate, archive, or export features.
- Use the mobile map to view team positions, current device/team position, search places or coordinates, drop a coordinate pin, and navigate externally.
- Toggle mobile basemap and team-location layer preferences.

## Build Status

Partial but significant.

Desktop has a real map window, feature model, repository/service layer, drawing tools, team markers, search, bottom panel, and feature actions. It is not just a placeholder. However, several GIS-suite concepts are still incomplete: File/Layers/View ribbon tabs are stubs, timeline/downloads are stubs, vertex editing/move/change style/convert are coming soon, and full layer management still needs design.

Mobile has a practical operational map focused on team locations, current device location, search, basemaps, coordinate pins, and navigation handoff. It does not appear to support editing incident spatial features.

## Screens And UI Inventory

- Desktop: Incident Map window.
- Desktop: Ribbon with Home, Incident, File, Layers, View tabs.
- Desktop: Map canvas.
- Desktop: Contextual strip for selected features.
- Desktop: Bottom panel with Feature Table, Search Results, Coordinates, Timeline, Downloads, Log.
- Desktop: Buffer dialog.
- Desktop: Feature inspector / spatial objects supporting panels.
- Desktop: geometry summary widget.
- Mobile: Map screen.
- Mobile: map search bar.
- Mobile: layers/basemap bottom sheet.
- Mobile: team detail bottom sheet.
- Mobile: coordinate/search point action sheets.

## Links To Other Modules

- Teams: desktop and mobile maps show team locations.
- Tasking: task locations can be geocoded/linked to map objects; map can zoom to tasks.
- Safety: hazard zones and safety spatial adapters connect hazards to map geometry.
- Intel/Weather: intel records can carry locations; weather stations/locations are spatial context.
- Communications: repeater sites and communications spatial adapters connect comms infrastructure to the map.
- Logistics/Facilities: facilities, landing zones, check-in/access points, and resource locations belong on the map.
- Command: command dashboard includes a geographic snapshot and map expansion shortcut.
- Mobile tracking: mobile location-tracking settings feed the map.

## Desktop Experience

Desktop is the richer GIS authoring and coordination surface.

The desktop map is a standalone top-level window with its own ribbon, not a normal docked panel. It is built for larger-screen map work: drawing, selecting, buffering, searching, and inspecting spatial features. The map canvas uses Leaflet and persists user view state.

The experience is promising but still mid-build. The implemented feature/drawing tools should be treated as current-state, while the broader ribbon tabs and some selected-feature actions are explicitly unfinished.

## Mobile Experience

Mobile is a field awareness map.

It prioritizes seeing team locations, seeing the user's current tracking location, searching for teams/addresses/coordinates, dropping coordinate pins, changing basemaps, copying coordinates, and launching external navigation. It refreshes team locations periodically and stores map preferences locally.

Mobile does not currently expose desktop-style feature editing, operational geometry creation, or layer administration.

## Current Gaps

- Desktop File/Layers/View ribbon tabs are placeholders.
- Desktop timeline/downloads bottom tabs are placeholders.
- Desktop vertex editing, move, convert, and change-style actions are not implemented.
- Mobile does not edit shared incident spatial features.
- Layer management and layer visibility semantics need product design.
- Relationship between facilities, tasks, hazards, comms sites, intel items, and map features needs a customer-facing model.
- Offline map/download behavior is not complete.
- Desktop and mobile maps do not yet feel like one shared map product with the same layer vocabulary.

## Design Questions

- What is the canonical map object model: feature, layer, facility, hazard zone, task location, team location, planning sketch, operational point?
- Which modules can create map features, and which can only link to them?
- Should mobile users be allowed to create pins, hazards, clues, or task locations?
- What map layers are required for an operational period briefing?
- How should map data be exported, printed, or included in IAP/planning products?
- What offline map capability is required for field use?
- How should team tracking privacy, visibility, and retention be handled?

## Future Design Ideas

- Unified layer manager shared conceptually between desktop and mobile.
- Mobile field pin/observation capture with later promotion to intel, safety, task, or logistics records.
- Operational map packets for IAP products and briefings.
- Offline map downloads and incident-area cache management.
- Map-linked timeline showing task, team, intel, safety, and communication events over time.
- Clear feature detail pages that show linked records across modules.
