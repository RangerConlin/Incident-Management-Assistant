# Team Location Tracking — MVP Plan (GIS Module Phase 1)

## Goal

Show a single dot per team on a simple desktop map window, sourced from GPS
captured by whichever mobile device is logged in for that team. Background
tracking (location keeps reporting while the app is backgrounded), no
breadcrumb trail — only the most recent position per team is stored/shown.

**This map window is Phase 1 of the (currently unbuilt, see Decisions log)
full GIS module** — a real tile basemap with pan/zoom, living in
`modules/gis/`, that later phases extend with polygon drawing, assignment
areas, and `spatial_features` integration rather than a second, unrelated
map being built later. For this phase specifically, scope stays limited to
tile basemap + pan/zoom + team markers — no drawing tools or spatial-feature
wiring yet, but the panel is the intended foundation, not throwaway.

## Explicit scope

**In scope:**
- One location per `team_id` (not per person).
- Background GPS capture on mobile (app doesn't need to be foregrounded).
- Tracking is **manually started/stopped** by the user, never automatic
  (not tied to login/logout).
- When multiple team members are tracking, the **team leader's device is
  preferred**; while the leader is actively tracking, all other members'
  locations are dropped for that team's dot.
- Desktop map **window**: standalone panel with a tile basemap, standard
  pan/zoom manipulation, and one marker per team, refreshed live. Nothing
  else — no drawing tools, no layers beyond the basemap and team markers.

**Out of scope for this phase (later GIS-module phases, not "never"):**
- Polygon/point drawing, assignment-area management, `spatial_features`
  CRUD UI. None of this meaningfully exists today (see Decisions log) —
  building it is a separate, much larger effort that comes *after* this
  phase, on top of the same map panel this phase builds.
- Per-person markers/tracking.
- Breadcrumb/history trail — only last-known position is persisted.
- Geofencing, motion-based alerts, offline map tiles. Tracelet already has
  solid *polygon* geofencing support (enter/exit/dwell detection, native
  on-device evaluation, automatic handling of OS geofence-count limits) —
  a natural fit once a later phase adds real assignment polygons to check
  against. Not attempted here.
- Mobile-side map UI (mobile only *captures* location; it does not display a map).
- Formal mobile auth/session tokens — location submission piggybacks on the
  existing loose `team_id`-based trust model already used by the rest of the
  mobile API (see `Current Mobile API Contract.txt` in the desktop repo).

## Package decision — mobile background location

Use **`tracelet`** (pub.dev, Apache 2.0, verified publisher `ikolvi.com`,
160 pub points, ~5.9k weekly downloads as of 2026-07). Reasons:
- Purpose-built for exactly this scenario: Android foreground service +
  iOS background modes, SQLite offline persistence, automatic HTTP sync on
  reconnect (field teams routinely lose signal), motion-based GPS throttling
  for battery.
- Free/open-source, unlike `flutter_background_geolocation` (the more
  battle-tested but paid alternative — keep as a fallback if Tracelet proves
  unreliable in testing).
- Rejected `flutter_background_tracker_pro` (unverified publisher, 41
  downloads, essentially unvetted) and rolling our own on top of bare
  `geolocator` (would require hand-building the offline-queue/retry logic
  Tracelet gives for free).

**Risk to track:** Tracelet is young and has shipped breaking changes twice
already (2.0.0, 3.2.0). Pin the exact version in `pubspec.yaml` and budget
extra integration-test time rather than assuming zero surprises.

## Mobile changes (`ICS-Mobile-App`)

1. Add `tracelet` (pinned version) to `pubspec.yaml` dependencies.
2. Android: `android/app/src/main/AndroidManifest.xml` — add
   `ACCESS_FINE_LOCATION`, `ACCESS_BACKGROUND_LOCATION`,
   `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_LOCATION` permissions per
   Tracelet's setup docs.
3. iOS: `ios/Runner/Info.plist` — add
   `NSLocationAlwaysAndWhenInUseUsageDescription`,
   `NSLocationWhenInUseUsageDescription`, and the `location` entry under
   `UIBackgroundModes`.
4. New permission-request screen/flow. No existing precedent to copy —
   `lib/screens/notification_permission_prompt.dart` (FCM permission) is the
   closest analog for UX structure, but location's "Always Allow" prompt
   needs its own explanation copy (why background tracking matters for
   field safety) before triggering the OS dialog.
5. **Tracking is manual, not automatic** — login does not start it. Add a
   toggle to `lib/screens/settings_screen.dart`, alongside the existing
   Battery Saving Mode toggle (currently local-state-only per prior
   scaffolding), that starts/stops Tracelet on demand. No new screen
   needed — this is the natural existing home for a device-behavior
   switch. Persist the toggle state (e.g. via `SessionStore` or
   `shared_preferences` directly) so tracking resumes automatically if the
   app is killed and relaunched while the user had left it on — but never
   auto-*starts* it from an off state.
6. Configure Tracelet's HTTP sync target to
   `POST /api/mobile/location` on the desktop server (see below), with the
   device's push token, `lat`, `lon`, `timestamp` in the payload — the
   server resolves person/team from the token server-side, so mobile
   doesn't need to send `team_id` on every ping. Set the report interval
   to a fixed **30 seconds** for now — no distance filter or motion-based
   throttling yet. Tracelet's motion-detection polling (suspend GPS when
   stationary, resume on movement) is a good follow-up once the basic feed
   is working, not part of this MVP pass.
   **Backlog / field usability:** the Android foreground-service
   notification must be silent/low-importance. It is acceptable for tracking
   to show a persistent notification, but it must not vibrate, buzz, or behave
   like a new attention-demanding alert every time the phone wakes or is
   touched.
7. Stopping tracking (via the Settings toggle, or on logout via
   `SessionStore.clear()`) must call a stop endpoint (e.g.
   `POST /api/mobile/location/stop`, token-keyed) in addition to stopping
   Tracelet locally — the backend needs an explicit signal that this
   device stopped, not just a gap in ping timestamps, so the leader
   preference logic (backend section below) can react immediately rather
   than waiting for staleness to be inferred.

## Backend changes (`Incident-Management-Assistant`)

1. **Location lives directly on the team's own `TEAMS` doc** — no
   per-person location storage anywhere. Add
   `current_location_lat`, `current_location_lon`,
   `current_location_updated_at`, and `current_location_person_record`
   (which person is the current source — needed for the leader-override
   check in item 2) to `IncidentCollections.TEAMS`
   (`data/db/sarapp_db/api/routers/operations.py`).
2. `CHECKINS` is used **only to resolve identity**, never to store
   location: `token` → `push_tokens` row (`person_record` + `incident_id`,
   already stored there) → that person's `CHECKINS` doc → `team_id`
   (`checkin.py:288`). No new fields needed on `push_tokens` or `CHECKINS`.
3. New endpoints in `data/db/sarapp_db/api/routers/` (both currently
   listed as "planned but not implemented" in
   `Current Mobile API Contract.txt` — this closes that gap):
   - `POST /api/mobile/location`: accepts `token`, `lat`, `lon`,
     `timestamp`. Resolves `person_record` → `team_id` per item 2. If that
     `person_record` has no `CHECKINS` doc for the incident (never checked
     in), silently ignore the ping — no error back to the device, just
     don't write anything. Otherwise, check whether this person is the
     team's `leader_person_record` (on the `TEAMS` doc,
     `operations.py`'s `_resolve_leader` already reads this field — reuse
     it):
     - **Leader pinging**: always overwrite the team's
       `current_location_*` fields with this ping and set
       `current_location_person_record` to the leader.
     - **Non-leader pinging**: overwrite only if
       `current_location_person_record` is *not* the leader (i.e. the
       leader isn't the current source) — otherwise ignore this ping, the
       leader's dot stays.
   - `POST /api/mobile/location/stop`: accepts `token`. Resolves
     `person_record` the same way. If this person is the current
     `current_location_person_record` for their team, **clear** the
     team's `current_location_*` fields (the dot disappears — no fallback
     search for another tracking member; tracking is manual, so an empty
     state here is correct, not a bug). If this person wasn't the current
     source, do nothing.
4. **Auto-stop on sign-out/demob.** Tracking must stop the moment a
   tracking person leaves field-active status, without waiting for the
   mobile device to say so (IC staff may demobilize someone from the
   desktop while their phone is still pinging):
   - `PATCH /{person_record}/status` (`checkin.py:549`, `update_status`) —
     when the incoming status is `"Demobilized"` (`checkin.py:234`): if
     this person is their team's current `current_location_person_record`,
     clear the team's `current_location_*` fields as part of the same
     write (same "clear, don't fall back" behavior as the stop endpoint).
     `"Preparing for Demobilization"` stays in the checked-in/tracking-
     eligible set (`checkin.py:22`) — only the terminal `"Demobilized"`
     status stops tracking.
   - Mobile-initiated sign-out is already covered by item 3's stop
     endpoint (mobile calls it on logout, see mobile item 7) — this
     backend rule is the server-side backstop for when mobile isn't the
     one initiating the change.
5. **New GET endpoint**: `GET /api/incidents/{incident_id}/team-locations`
   — returns every team's `team_id` and `current_location_lat/lon/
   updated_at` straight off their `TEAMS` docs (omitting teams with no
   current location). This is what the desktop panel calls once on open
   to draw the initial set of markers, before live websocket updates take
   over. Since every write already lands on `TEAMS` via `BaseRepository`,
   the existing websocket hub broadcasts these changes automatically — no
   extra realtime plumbing needed for live updates either.
6. Update `Current Mobile API Contract.txt` to move the two mobile-facing
   endpoints (item 3) from "planned" to "implemented" once shipped.

## Desktop changes (`Incident-Management-Assistant`)

1. No map widget exists anywhere in the app today. Default approach is
   `QWebEngineView` + Leaflet/OpenStreetMap, but this is **not committed**
   — if `QWebEngineView` isn't cleanly available in the installed `PySide6`
   (may need `PySide6-Addons` or a separate wheel), fall back to an
   alternative Qt-native approach (e.g. a custom `QGraphicsView`/
   `QGraphicsScene` tile renderer, or `pyqtlet2`) without re-planning the
   rest of this doc — the panel/websocket wiring below is agnostic to
   which widget renders the map. Leaflet (or whatever alternative is used)
   gives pan/zoom for free as baseline behavior — no custom manipulation
   code needed to satisfy that requirement.
2. New panel: `modules/gis/panels/team_location_map_panel.py` — this is the
   **first real panel of the GIS module**, not a one-off. It does not
   integrate with `spatial_features` or the GIS adapters yet (those pieces
   don't work today — see Decisions log), but the map widget it stands up
   is meant to be the one later phases extend with drawing tools and
   spatial-feature layers, not replaced by a different map widget later.
   Scope for this phase: render the basemap, plot one marker per team,
   support pan/zoom. No drawing, no editing, no other layers yet.
3. Load the initial marker set from `GET /api/incidents/{incident_id}/
   team-locations` (backend item 5) on panel open. Subscribe to the
   incident's websocket feed (same hub used elsewhere) for live updates —
   since every ping already writes straight onto the team's `TEAMS` doc
   (backend item 3), the desktop panel just displays whatever it receives;
   it never touches leader-preference logic itself, that decision is
   already made by the time desktop sees it. A team absent from the
   response/update simply has no marker — not a stale last-known dot.
   **Backlog / map controls:** add a mobile map-screen button that forces
   the map orientation back to north-up.
4. Register the panel in the docking system (`PySide6-QtAds`).

## Implementation order & testing

- **Order**: backend first (nothing to point the mobile app or desktop
  panel at otherwise), then either side can proceed in parallel — mobile
  and desktop both only depend on the backend endpoints existing, not on
  each other.
- **Backend**: add `pytest` coverage for the two mobile endpoints (leader
  ping overwrites, non-leader ping ignored while leader is the source,
  non-leader ping accepted once leader isn't the source, unchecked-in
  person's ping silently ignored, stop clears only when stopper is the
  current source), the GET endpoint, and the demob auto-clear behavior —
  this repo's `agents.md` requires test coverage with every change.
- **Mobile**: run `flutter analyze` and `flutter test` per this repo's
  standard convention; the location feature itself can't be end-to-end
  tested in this sandbox (needs a real device for GPS + a live server),
  so call that out explicitly rather than claiming it was verified.

## Rough effort estimate

| Piece | Estimate |
|---|---|
| Backend (schema field + endpoint + contract doc update) | 0.5–1 day |
| Mobile (Tracelet integration, permissions, session wiring) | 4–5 days |
| Desktop (map widget + panel + websocket wiring) | 2–4 days |
| **Total** | **~7–10 developer-days** |

Mobile background tracking and the desktop map widget are the two
highest-uncertainty pieces — both are greenfield in their respective repos
today.

## Decisions log

- **Location storage**: no per-person location storage at all. Every ping
  writes directly onto the pinging person's team's `TEAMS` doc
  (`current_location_lat/lon/updated_at/person_record`), gated by an
  inline leader-preference check at write time (leader always overwrites;
  non-leader only overwrites if the leader isn't the current source).
  `CHECKINS` (`checkin.py`, via `push_tokens.person_record`) is used only
  to resolve which team a pinging person belongs to — never to store a
  location. Desktop only ever reads/watches `TEAMS` docs.
- **Map widget stack**: not committed to `QWebEngineView`. Try it first;
  swap to a Qt-native alternative if it's not cleanly available, no
  re-plan needed.
- **Report interval**: fixed 30 seconds for the MVP. Revisit once the feed
  is working — Tracelet's motion-detection polling is the likely next
  tuning step, not required now.
- **Multiple devices per team**: leader's ping always wins and overwrites
  immediately; a non-leader's ping only takes over if the leader isn't
  currently the source. If the leader stops (or is demobilized) while
  tracking, the team's dot **clears** — it does not automatically hand off
  to another tracking member. No stored per-person data to fall back to,
  and this matches tracking being manual-only elsewhere in this plan: no
  automatic hand-offs, full stop.
- **Tracking start/stop**: manual only, via a Settings toggle (mobile item
  5) — never auto-started on login. Auto-stopped server-side on
  demobilization regardless of device state (backend item 4), and
  explicitly stopped by the app on logout (mobile item 7).
- **Full GIS module status (as of 2026-07)**: confirmed essentially unbuilt,
  not just "unpolished scaffold." `spatial_features` is a working MongoDB
  collection (WKT geometry, source linkage) with two inspector panels
  (`feature_inspector_panel.py`, `spatial_objects_panel.py`), but there is
  no map, no polygon-drawing UI, no assignment-area creation flow, and the
  `task_spatial_adapter.py`/`team_spatial_adapter.py` linkage methods that
  would tie a polygon to a task/team are never called from anywhere. No
  point-in-polygon library (`shapely` etc.) is installed. **This MVP's map
  window is Phase 1 of building that module** — the basemap/pan-zoom panel
  it stands up is the foundation later phases extend with drawing tools
  and `spatial_features` integration, not a disposable stand-in. Auto-
  status-on-area-entry and dwell-time tracking (discussed but not planned
  here) are later-phase work once real assignment polygons and point-in-
  polygon logic exist on top of this panel.
