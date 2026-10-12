# GIS Module Feature Packages

## Purpose

Define the GIS module as a shared incident-mapping domain with separate
feature packages for:

- mobile field workflows (`ICS-Mobile-App`)
- desktop/web command workflows (`Incident-Management-Assistant` and any future web client)

This document is intentionally product-facing, not implementation-heavy. It
answers "what should the GIS module do on each platform?" before we commit to
screens, APIs, or sprint sequencing.

## Current baseline (2026-07-15)

What already exists or is directionally committed:

- A shared spatial feature model already exists on the server:
  `spatial_features` and `spatial_feature_links`.
- The desktop repo already has a GIS domain layer:
  feature registry, layer registry, spatial repository, adapters, and
  read-only inspectors.
- Phase 1 team tracking already exists as a narrower capability:
  mobile submits location, server stores one current dot per team, desktop
  renders those team markers on a Leaflet map panel.
- The GIS architecture direction is already leaning toward:
  Leaflet for map display/editing and server-side/headless analysis later.

What does **not** meaningfully exist yet:

- Full map authoring workflows
- Polygon/line drawing UX tied to operations workflows
- Layer toggles and styling UI
- Mobile map-based capture/editing
- Spatial analysis workflows
- Printable map production workflows

## Design principles

1. One GIS domain, two platform packages.
   The data model should stay shared even when the UX and capabilities differ.

2. Mobile is point-capture-first.
   Mobile GIS should prioritize field collection, awareness, safety, and
   navigation. Mobile authoring should stay point-based.

3. Desktop/web is authoring-and-coordination-first.
   Command-side GIS should own drawing, review, linking, monitoring, and map
   composition.

4. Feature packages should map to user jobs, not just technical layers.
   A package should represent a coherent workflow surface.

5. Mobile should not inherit every desktop feature.
   Capability parity is not the goal; operational usefulness is.

6. GIS ownership should stay narrow.
   GIS should own map-native products. Other modules can project onto the map
   without becoming GIS-owned records.

7. Organization should stay simple.
   Collections are folders, not a second taxonomy.

## Shared GIS foundation packages

These are cross-platform domain capabilities. They are not user-facing
packages by themselves, but both mobile and desktop/web should build on them.

### 1. Spatial feature domain

Core concepts:

- feature types
- geometry types
- source record ownership
- related-record links
- status, visibility, archive state
- timestamps and attribution

Must support:

- point, line, polygon geometries
- module-owned records linking into GIS
- feature filtering by type, module, owner record, and incident

### 2. Layer model and cartographic rules

Core concepts:

- multiple basemaps
- basemap stacking/overlay
- transparency/opacity control
- logical layer keys
- display groups
- default styles
- layer ordering
- visibility rules

Initial shared layer groups:

- basemaps
- teams
- tracks
- tasks
- assignments
- clues
- subjects
- hazards
- comm sites
- logistics sites
- planning overlays
- imported overlays

### 3. Realtime and sync contract

Core concepts:

- live updates from incident activity
- offline queue and replay rules for mobile-authored changes
- stale/archived state handling
- conflict policy

Minimum behavior:

- desktop/web can reflect live updates with minimal refresh friction
- mobile can safely capture offline and replay later where appropriate

### 4. Spatial linking package

Core concepts:

- link a feature to its owner record
- link additional related records
- expose "show related features" from non-GIS modules

This is the bridge that makes GIS operationally useful rather than becoming an
isolated map toy.

### 5. Geometry exchange package

Core concepts:

- export geometry and geometry-derived information to other modules
- import geometry or area definitions from other modules
- keep GIS usable as shared operational infrastructure rather than a closed map
  workspace

Known consumers/producers:

- tasking
- initial response
- POD calculators
- forms or calculators that depend on area/geometry values
- aviation planning outputs

### 6. Import/export contract

Core concepts:

- GeoJSON/KML/shapefile import targets
- map/export image output
- coordinate-sheet export for generated geometry
- GPS-compatible export for navigation devices when feasible
- future printable briefing-map output

## GIS-owned feature types

This is the current working list of first-class GIS products.

- team locations
- bearings
- task points
- task routes
- task areas
- search segments
- sectors
- search grids
- containment lines
- operational polygons
- geofence polygons
- planning overlays
- imported overlay references
- mobile map markers

Notes:

- Bearings are first-class GIS features.
- Search geometry such as grids, segments, containment lines, polygons, and
  rings are core SAR GIS products.
- Sectors are core GIS planning/search products.
- Geofence polygons are valid GIS-owned planning/control products.
- Desktop may support additional planning-only layers such as LPB rings,
  probability rings, and similar analysis products even when they are not
  mobile-authored.

## Categorization model

Geometry creation should stay consistent, but GIS items will need strong
categorization so they can behave differently without requiring a completely
different creation workflow for every item.

Core idea:

- create the geometry in a common way
- assign a category/subcategory
- let that category drive behavior, styling, filtering, export, and downstream
  module interactions

This matters because the same base geometry may need to act very differently
depending on whether it represents:

- a clue
- an assignment
- a picture/photo location
- a POI
- planning data
- a plaza or event map item

Category should influence:

- default styling
- layer placement
- filtering
- form/export behavior
- which modules can consume it
- which calculations or tools apply to it
- what labels or summaries it shows

Design guardrail:

- keep the geometry model relatively small
- use categories heavily where behavior differs
- only create a brand-new GIS feature type when it has genuinely unique
  generation logic, calculations, or workflow

## Map-visible but not GIS-owned

These records may appear on the map when they have a location or geometry, but
they remain owned by their home modules.

- clues with location
- hazards with a GIS component
- other external records with map location or geometry

Notes:

- Hazards are never GIS-owned.
- Some hazards may render as a point, buffer, or polygon.
- Many hazards may have no GIS component at all.
- Clues most likely associate to GIS only by having a location.

## Organization and filtering

Keep this intentionally simple.

Core dimensions:

- task
- team/creator when relevant
- folder
- operational period

Folder behavior:

- create folder
- name folder
- place object in folder

## Mobile GIS feature packages

Mobile packages should assume:

- smaller screens
- intermittent connectivity
- battery sensitivity
- lower editing precision
- field users acting under time pressure

Authoring rule:

- mobile creates points only
- mobile may view desktop-authored non-point geometry

### M1. Field Tracking Package

Primary job:
Let a field team deliberately share its location with command.

Core features:

- manual start/stop location tracking
- background GPS reporting
- team-based tracking identity
- clear tracking state in settings and session UX
- "tracking active" safety/status feedback

Deliberately excluded:

- per-person breadcrumb display
- multi-layer map editing
- command-side monitoring tools

Future idea:

- alternate tracking feeds such as Meshtastic-based position reporting

### M2. Field Awareness Map Package

Primary job:
Let responders see the incident geography that matters to them right now.

Core features:

- read-only map view on mobile
- own team location
- assigned task point/route/area
- search segments, sectors, grids, containment lines, and other desktop-authored
  planning geometry when relevant
- relevant hazards and closures
- check-in points, med units, staging/base locations
- last-known teammate/team context if operationally useful

Optional later features:

- lightweight layer toggles
- coordinate readout
- basemap switcher

Not first-wave:

- full GIS editing
- dense multi-layer command dashboard behavior

### M3. Point Capture Package

Primary job:
Create point-based GIS items from the field with as little friction as
possible.

Core features:

- add mobile map markers
- capture bearings
- capture coordinate from current GPS
- optionally auto-link to the current task when the team is assigned
- submit or queue offline

Later expansion:

- additional point subtypes if a real field workflow appears

Guardrail:
Mobile capture should favor quick point workflows over freeform GIS authoring.

### M4. Offline Map and Sync Package

Primary job:
Keep field GIS usable when the network is unreliable.

Core features:

- cache mission-relevant map data
- cache assigned overlays and operational layers
- queue outbound captured features
- visible sync state and retry behavior

Open design note:
Offline map tiles and offline feature sync can be separate sub-packages if we
want to ship data sync before full offline basemaps.

### M5. Field Navigation Package

Primary job:
Help a team move to and through an assignment safely.

Core features:

- route-to assignment or waypoint
- distance/bearing to target
- route overlay display
- optional off-route indication

Later expansion:

- terrain-aware routing
- avoid hazard/closure areas
- route suggestions from command-authored geometry

### M6. Assignment Compliance Package

Primary job:
Help the team understand its geographic operating boundaries.

Core features:

- show assigned sector/assignment boundary
- show geofence polygons when relevant
- warn when outside assigned area
- optional entry/exit event logging

Dependency:
Requires reliable polygon assignment geometry from desktop/web authoring.

## Desktop/Web GIS feature packages

Desktop/web packages should assume:

- larger screen real estate
- higher operator precision
- multi-panel workflows
- command/planning ownership
- stronger need for review and coordination tools

Authoring rule:

- desktop creates points, lines, polygons, rings, and other planning geometry
- desktop owns broad geometry authoring and editing

### D1. Command Map Workspace Package

Primary job:
Provide the main live incident map used by command and planning.

Core features:

- multi-layer map canvas
- multiple basemap support
- basemap overlay with adjustable transparency
- live team markers
- task and assignment overlays
- search grids, segments, rings, containment lines, and planning overlays
- hazard/intel/logistics overlays
- filter/search/highlight workflows
- incident-centric map navigation

This should be the central GIS shell the other desktop/web packages extend.

### D2. Layer Management Package

Primary job:
Control what the command map shows and how it is organized.

Core features:

- layer list/tree
- basemap picker
- basemap overlay opacity control
- layer presets
- label visibility controls
- visibility toggles
- ordering/grouping
- style presets
- saved layer states/views

Later expansion:

- role-based default layer presets
- per-op-period map views

### D3. Spatial Authoring Package

Primary job:
Create and edit operational geometry.

Core features:

- create point/line/polygon features
- create rings and other planning geometry
- create grids from a defined area and chosen cell size
- generate aviation search patterns from a starting point
- split and merge segments or other area geometry
- edit geometry and metadata
- assign feature type and layer
- archive/lock/hide features
- snap or validate geometry as needed
- snapping and alignment tools
- undoable generation workflows

High-priority authoring targets:

- assignment areas
- task points/routes/areas
- search grids, segments, and sectors
- grid-based assignment geometry
- containment lines
- geofence polygons
- rings and other SAR planning products
- aviation search patterns
- hazards/closures
- logistics/support locations

### D4. Operational Linking Package

Primary job:
Connect GIS geometry to the rest of incident operations.

Core features:

- link features to tasks, teams, hazards, intel records, and logistics sites
- open source record from map selection
- show related features from source records
- support one owner plus additional related links

This is the package that turns drawn geometry into operational context.

### D5. Live Tracking and Dispatch Package

Primary job:
Use live movement/location data in command workflows.

Core features:

- current team positions
- tracking freshness and source status
- filter by team/task/status
- quick actions from selected team marker
- future track history playback if/when stored

Not required for phase 1:

- breadcrumb storage
- predictive movement analytics
- alternate radio/mesh tracking integrations such as Meshtastic

### D6. Planning and Analysis Package

Primary job:
Support incident planning decisions with spatial tools.

Core features:

- easy feature search
- easy POI/place search
- area-based feature and POI queries
- measurement tools for distance, bearing, area, and perimeter
- auto grid creator from area plus selected grid size
- quick conversion of UTM/USNG/CAP grid references into search areas
- search segments and grids
- sector planning
- containment and boundary planning
- geofence polygon planning
- LPB rings and probability/planning rings
- buffer generation around points, lines, and polygons
- aviation search pattern generation from a starting point
- generation of turn-point coordinates for export sheets
- route and leg distance calculations
- route and leg estimated time calculations
- assignment labeling tools
- route planning overlays
- simple buffer/intersection checks
- imported overlay references

Later expansion:

- datum and drift tools
- terrain/viewshed analysis
- probability or coverage overlays
- clue heatmap or similar analysis views if they prove operationally useful
- more formal geoprocessing

Grid creator notes:

- support standard preset grid sizes
- allow custom grid sizes
- generated grid cells should be immediately usable for assignment workflows
- sectors should also be directly usable for assignment workflows

Aviation pattern notes:

- generate search pattern geometry from a selected starting point and chosen
  pattern settings
- support standard patterns including creeping line, expanding square, and
  sector search
- all pattern variables should be user-modifiable
- provide standard presets for common pattern setups
- export a coordinate sheet listing turn points
- support GPS-compatible export formats for aircraft GPS upload when practical

Tasking dependency:

- the tasking module will need an area-assignment capability so generated
  grids, segments, and other area products can flow directly into tasking
- some forms will also need area-aware calculations driven from assignment
  geometry

Cross-module dependency:

- GIS geometry and geometry-derived information will need to move into and out
  of multiple modules, including tasking, initial response, and POD
  calculators

### D7. Print, Export, and Sharing Package

Primary job:
Turn the operational map into outputs others can use.

Core features:

- saved map views and bookmarks
- export current map view
- export selected layers/features
- print/export templates for briefing maps
- briefing-map output
- shareable incident map links for web

Likely split:

- desktop owns printable production first
- web owns shareable/read-only access first

### D8. Administration and Data Ingest Package

Primary job:
Bring external spatial context into the incident map and keep it governable.

Core features:

- import external overlays
- validate geometry/source metadata
- layer/category assignment on import
- archive and provenance controls

### D9. Cross-Module Geometry Workflows Package

Primary job:
Make geometry immediately usable across the rest of incident operations.

Core features:

- create task from selected geometry
- show geometry for a selected task
- geometry-derived summaries for downstream forms and calculators
- basic geometry revision awareness when assignment areas or planning geometry
  change

## Planned-event GIS tools

Planned events use the same GIS foundation, but the tool emphasis shifts away
from search geometry and toward venue operations, public flow, access control,
and safety layout.

### Core planned-event map products

- venue or event footprint boundaries
- parking areas
- ingress and egress routes
- pedestrian flow corridors
- barricade or closure lines
- checkpoints and access control points
- command posts and branch/division locations
- first aid, medical, and reunification points
- shuttle, staging, and transportation areas
- evacuation routes and shelter points

### Planned-event planning tools

- crowd flow route and corridor planning
- access control zone planning
- road closure and detour planning
- parking and shuttle area layout
- emergency egress and evacuation planning
- temporary facility placement
- venue perimeter and inner security ring planning
- buffer generation for safety and standoff planning

### Planned-event operational queries

- identify facilities, transport nodes, or support locations within an area
- find all checkpoints, medical points, or closures affecting a route
- show all assets or control points inside a venue section

### Planned-event mobile relevance

Mobile does not need a separate geometry-authoring model here.
The same mobile rules still apply:

- point-based mobile creation only
- mobile viewing of desktop-authored planned-event geometry
- field awareness of routes, checkpoints, closures, and assigned areas

## Recommended package boundaries by platform

### Mobile first-wave packages

Recommended first mobile set:

- M1 Field Tracking
- M2 Field Awareness Map
- M3 Point Capture
- M4 Offline Map and Sync

Reason:
These are the highest-value field workflows and align best with mobile device
capabilities.

### Desktop/web first-wave packages

Recommended first desktop/web set:

- D1 Command Map Workspace
- D2 Layer Management
- D3 Spatial Authoring
- D4 Operational Linking
- D5 Live Tracking and Dispatch

Reason:
These create the command-side system that mobile workflows depend on and make
the shared GIS data model truly usable.

## Capability asymmetry we should preserve on purpose

Things desktop/web should own that mobile should not try to fully replicate:

- dense multi-layer command view
- full polygon/line authoring
- ring and planning-geometry authoring
- bulk editing and review workflows
- import/governance workflows
- print/export composition
- heavier analysis

Things mobile should own that desktop/web should not lead:

- background location capture
- fast point-based capture
- offline-first queueing behavior
- low-friction field safety prompts

## Suggested next design artifact

The next useful step is a package-by-package feature matrix with columns:

- package name
- primary user
- core user jobs
- must-have features
- explicitly excluded features
- server dependencies
- offline requirement
- phase target

That would let us turn this into an actual build plan without losing the
platform split.

## Rollout tiers

This module is feature-rich enough now that it needs a realistic delivery
sequence.

### Core v1

The first release should focus on the smallest coherent system that is
immediately useful in operations.

#### Mobile v1

- team tracking
- read-only awareness map
- point-only creation
- bearing capture
- mobile map markers
- view assigned task geometry
- view hazards/clues when they have map representation
- offline queueing for point-based submissions

#### Desktop/web v1

- command map workspace
- multiple basemaps
- basemap overlay with transparency control
- layer visibility controls
- folder support
- operational period filtering
- live team positions
- create points, lines, polygons, and rings
- create and edit task areas
- create and edit search grids
- create and edit segments
- create and edit sectors
- create and edit containment lines
- create and edit geofence polygons
- measurement tools
- buffer generation around points, lines, and polygons
- easy feature search
- easy POI/place search
- area-based queries
- create task from geometry
- show geometry for task

#### Cross-module v1

- tasking area-assignment support
- geometry export to tasking
- geometry exchange with initial response where needed
- geometry-derived area values for modules/forms that depend on them

Core v1 goal:

- create, view, organize, and operationalize mission geometry without needing
  ad hoc workaround tools

### Near-term follow-on

These features materially improve planning power, but the system is still
usable without them on day one.

#### Mobile near-term

- field navigation support
- assignment compliance using desktop-authored polygons/geofences
- lightweight layer toggles if mobile clutter remains manageable

#### Desktop/web near-term

- layer presets
- label visibility controls
- saved map views/bookmarks
- print/export templates for briefing maps
- split and merge tools for segments/areas
- snapping and alignment tools
- undoable generation workflows
- assignment labeling tools
- route/leg distance calculations
- route/leg ETA calculations
- standard and custom grid-size workflows
- UTM/USNG/CAP grid reference to search-area conversion
- aviation pattern generator
- coordinate sheet export for generated geometry
- GPS-compatible export where practical
- planned-event operational tools built on the shared geometry model

#### Cross-module near-term

- richer geometry import/export with initial response
- POD calculator geometry exchange
- basic geometry revision awareness
- more complete downstream summaries for forms/calculators

Near-term goal:

- make the GIS module genuinely efficient for planners and specialized SAR
  workflows, not just usable

### Later and advanced

These are valuable, but should not block the first practical release.

- LPB rings and probability rings
- clue heatmaps or related analysis overlays
- terrain/viewshed analysis
- broader geoprocessing tools
- datum and drift tools
- Meshtastic or other alternate mesh/radio tracking feeds
- wider GPS/device export ecosystem support beyond initial practical formats
- any advanced automation built on geofence events

Later goal:

- expand from operational mapping into deeper analysis and automation once the
  core workflows are stable
