**************************************************************************************************************
[Command]
Incident Command Dashboard

Incident Overview 
   
Incident Organization

SITREP Window

- Command Dashboard redesign (modules/command/widgets/ic_overview_widget.py, 2026-07-21) has four
  panels still shipped as empty states because none of them have a backing data model yet. Each
  needs a real repository/schema/API route before it can show real data instead of a placeholder:
  - Pending Approvals panel — no approval/workflow data model exists (resource request approvals,
    task extension approvals, comms channel change requests, etc. aren't tracked as a queue
    anywhere). Needs a schema for an approvable "request" concept plus approve/deny actions wired
    to whatever module originated the request.
  - Section Health panel — no per-section (Operations/Planning/Logistics/Communications/Safety/
    Intel/Liaison/Finance) status tracking exists. Needs a data model for section-level status
    (e.g. good/caution/critical) plus a note field, and a way for each section lead to update it.
  - Operational Period Readiness panel — no ICS-form completion checklist (202/203/204/205/206,
    safety message, briefing packet, resource gaps review, etc.) is tracked anywhere. Needs a
    per-operational-period checklist model, likely derived from whether each ICS form/module has
    been completed for the current OP rather than a manually maintained list.
  - Recent Major Activity panel — no unified cross-module activity/audit feed exists to pull from.
    Needs either a dedicated incident-wide activity log collection that other modules write to, or
    an aggregation query across existing per-module logs.
  - The three KPI tiles for Personnel Checked In, Open Leads, and Safety Issues are placeholders
    for the same reason (no data source) and should be revisited alongside Section Health/Safety
    once those data models exist.

- Incident Organization (ICS-203) positions, 2026-10-20: standard command/general-staff titles
  that the approval engine's escalation table matches by exact string (Safety Officer, Incident
  Commander, Communications Unit Leader, Medical Unit Leader, the other section chiefs/unit
  leaders in `server/sarapp_db/sarapp_db/api/routers/approvals.py`'s `_ESCALATION`/`_SPECS`)
  should be hardcoded, non-editable position titles rather than freeform text, so a rename or
  typo can't silently break role-based approval resolution. Custom org-chart nodes (branches,
  divisions, groups, units) stay freeform as today — this only applies to the fixed set of
  command/general-staff roles the approval engine looks up by name.
  - Positions should be referenced by FK int, not strings.  Names may change but FKs will not
**************************************************************************************************************
[Planning]
Planning Dashboard

Operational Period Manager

Demobilization Planner

Meeting Planner

Individual Meeting Detail Windows

**************************************************************************************************************
[Operations]
Operations Dashboard

Operations Section Organization

Team Status Board

Task Board
  - Remove the location type field - should be automatically determined by the entry 
**************************************************************************************************************
[Team Detail Window]
  - Usability redesign needed (modules/operations/teams/panels/team_detail_window.py, 2026-10-05) —
    the window has grown tab-by-tab (Personnel/Vehicles/Equipment/Logistics/Logs/Safety) without a
    pass on overall layout/flow; revisit information hierarchy and navigation once there's time to
    design it properly rather than keep bolting tabs on.
    -- Confirmed unusable in practice for the new GAR Safety tab (modules/operations/teams/panels/gar_editor.py,
       2026-10-05): the dynamic group/row/combo-box layout doesn't fit well in the window as built. GAR
       editor UX needs to be redesigned alongside the window redesign, not patched in isolation.

**************************************************************************************************************
[Task Detail Window]
  - Communications channels need a selector for channel type (primary/alternate/etc)
  - 104/109 exports need to be tied to a specific team somehow
  - Safety tab GUI redesign needed (modules/operations/taskings/task_detail_widget.py, 2026-10-05) — the
    tab now stacks a free-text safety summary, the TeamGarRollupPanel (team GAR roll-up,
    modules/operations/taskings/team_gar_rollup.py), and the HazardAnalysisEditor (linked hazard SPE
    notes, modules/planning/tactics_resources/widgets/hazard_analysis_editor.py) in one plain vertical
    column with no real layout pass. Needs an actual information-hierarchy design, not three widgets
    stacked in a QVBoxLayout.

**************************************************************************************************************
[Logistics]
Logistics Dashboard

Check In ICS-211
    
Resource Status Board


Facilities Manager

- Dashboard redesign mockup (Design Documents artifact, 2026-07-20) replaced the old ad-hoc
    Supply & Comms Health badges (PPE/Medical/Water/Fuel/Comms Cache/Spare Radios) with the same
    panel unchanged, pending a real tracking system: today those levels aren't backed by any
    repository/collection, so before building this panel for real we need to decide how supply
    and comms-cache stock levels get recorded and updated (manual entry vs. derived from
    check-in/checkout and resource request activity) and what collection/schema should hold it.


**************************************************************************************************************
[Communications]
Communications Dashboard

Communications Plan ICS-205

Communications Log (ICS 309)

Log Entry

Quick Entry

Chat Messages

ICS-213 Messages

Notification Feed

Notification Settings
**************************************************************************************************************
[Intel]
Intel Dashboard

Subjects

Leads

Intel Items

Assessments

Intel Logs

Forms

- Weather module rebuild (modules/intel/weather/, 2026-07-22) — see modules/intel/weather/backlog.md
  for the module's own follow-ups: lightning data deferred (no reliable free API); NWS location-code
  hint caching (location_codes.py) isn't wired back into the new WeatherManager yet (forecast/HWO
  still work, just without the caching speedup).
**************************************************************************************************************
[Safety]
  - Restore Safety Analysis Templates as reusable groupings of master hazard library entries for quick import into the tactics/planning workflow.
    -- Keep `hazard_types` as the single source of truth; templates only store grouped hazard selections, ordering, and any import-oriented metadata needed by planning/tactics.
Safety Message ICS 208

Incident Safety Analysis ICS 215A

CAP Operational Risk Management CAPF160

Incident Report (IWI)

**************************************************************************************************************
[Medical]
Medical Plan ICS 206

- ICS-206 Hospitals "Find Nearby" has no trauma-level or burn-center data source, 2026-09-19.
  The nearby-hospital search is backed by CMS Hospital General Information (has
  emergency_services Yes/No, geocoded and cached per state), but CMS carries no trauma
  level, pediatric trauma level, or burn-center designation, so the preparer must fill
  those fields in by hand after adding a hospital. No free, queryable, nationally
  consistent source was found for this (ACS's verified-trauma-center list is a search
  page with no download; EMNet/findERnow's national database is researcher-access-only
  or paid; the American Burn Association's verified-burn-center list is a directory page
  with no bulk download/API found; HIFLD's TRAUMA field is stale and inconsistently
  formatted). State health department trauma-designation lists (e.g. Michigan MDHHS
  publishes a PDF) are the most promising free/official route but are state-by-state,
  manually downloaded, and would need a one-time importer that matches each state list
  to CMS hospitals by name/city and flags unmatched rows for manual review. Needs a
  decision on which state(s) to prioritize and whether to build the matching importer.

**************************************************************************************************************
[Liaison]
  - Web/API gaps: contacts and interactions support creation but no edit/delete endpoints;
    restrictions, agreements and follow-up records have no write endpoints. Add shared
    repository-backed CRUD before enabling those controls in the web client. Unified Liaison
    activity logging remains unmodeled; interaction logging is available separately.
  - liaison.py still runs _ensure_int_ids during reads and writes missing identifiers directly
    through raw collections. Replace with a one-time canonical-ID migration, then remove
    runtime repair writes. The older agency-requests/resource-offers/feedback collections still
    coexist with the newer liaison_requests workflow and need a deliberate migration plan.
  - Remaining gap: Agency Detail dialog's Contacts / Restrictions / Agreements tabs are
    read-only (backend supports Contacts CRUD; Restrictions/Agreements have no create UI at
    all) — add "add" dialogs for these if the LNO workflow needs them tracked.
**************************************************************************************************************
[PIO]
- Shared API hardening: public_information.py still writes messages, revisions, templates,
  generic records, and media response links directly to raw Mongo collections. Move these
  writes to BaseRepository subclasses; add server-enforced lifecycle transitions and edit
  constraints (the web UI follows desktop transitions but the API currently accepts arbitrary
  statuses/edits). Preserve approvals and publication metadata on saves at the API boundary.
  Generic misinformation saves also default timeline to an empty array; preserve existing
  events server-side when a record update omits them. The web client currently retains the
  loaded timeline, but concurrent edit protection still needs API support. Summary updates
  currently rely on polling for cross-collection changes.
PIO Dashboard

Messages/Releases

Misinformation/Rumors

Media Log

Talking Points

Letterhead/Templates

Distribution Log

**************************************************************************************************************
[Finance]
Finance/Admin Dashboard

Time Tracking

Expenses & Procurement

Cost Summary

**************************************************************************************************************
[Personnel Edit Window]


**************************************************************************************************************
[Disaster Response Toolkit]

**************************************************************************************************************
[Planned Event Toolkit]

**************************************************************************************************************
[Initial Response]
  - Initial response initial window has a minimum height that exceeds the height of the monitor several times over.  In addition multiple tabs have broken formatting or things that dont translate to dark mode at all.  

**************************************************************************************************************
[Reference Library]

**************************************************************************************************************
[Dockable Widgets]

**************************************************************************************************************
[Tech Debt / Infrastructure]
    - Team Type Catalog follow-up: migrate incident teams from free-text
      `team_type` to stable catalog ids with incident-owned version snapshots;
      then remove the remaining code-keyed operational field. Catalog definitions
      are already consumed across desktop, web, and mobile; desktop GIS also uses
      the catalog icon and aviation fields. Do not add fallback reads or a
      compatibility layer.
    - Web client (`apps/web/`): full-CRUD browser clone of the desktop app, built module by module — see
      `apps/web/AGENTS.md` for conventions and `src/shell/moduleRegistry.ts` for the full module list and
      which are live.
      - Auth is not enforced anywhere (`POST /api/auth/login` issues a JWT; no router checks it). A
        tunnel-scoped enforcement design (require it only on requests that arrived via `cloud_router`'s
        public tunnel) was tried and reverted: the LAN tunnel is currently broken, so real desktop/mobile
        traffic already arrives looking tunnel-sourced — enforcing on that signal today would mean
        requiring auth everywhere immediately, with no way for those clients to send a token. Whoever
        picks this up needs to either fix the LAN tunnel first (so that signal means what it should) or
        treat it as a coordinated multi-client rollout (desktop + mobile + web all need a login path
        before enforcement can flip on anywhere) — a middle path is building the verification dependency
        disabled by default (env-var gated) so it's ready once that rollout happens. Also still needed: a
        password reset/change flow (`/password/set` only works once per account today). See
        `docs/archive/design-documents/Instructions/database_architecture.md` ("Authentication").
      - `linked_strategy_summary` (one of desktop's Task Status Board columns) is deliberately not
        exposed via `GET .../operations/task-rows` — it needs a real extra HTTP round-trip per task into
        a Planning-module endpoint, a cross-module dependency on a module with no web presence yet.
        Revisit once Planning gets its own web pass.
      - Team Detail's Personnel/Vehicles/Equipment tabs edit the team's `members_json`/`vehicles_json`/
        `equipment_json` arrays as plain strings (add/remove a name or ID), not against the
        Personnel/Logistics master catalogs — those aren't wired up to the web client yet. Revisit once
        those modules get their own web pass.
      - The app's own bundle can't be reached through a `/r/<code>/app/...` connect-code URL yet:
        `apps/web/vite.config.ts`'s `base: "/app/"` bakes absolute asset paths into `index.html`, which
        lose the `/r/<code>` prefix when a browser resolves them (`cloud_router` strips that prefix on the
        request it proxies, but doesn't rewrite the HTML it returns). `src/api/connection.ts`'s domain +
        connect-code setting only redirects data calls made after the app has already loaded, not the
        initial bundle load. Fix is likely a relative base path (or computing it at runtime from
        `document.baseURI`) instead of the hardcoded absolute `/app/`.
    - Optimization follow-up: profile Edit-menu windows and the task detail window to identify why modest datasets
      are not opening faster; tie this to any decision about reusing/caching Edit windows.
    - Sidebar: revisit large Edit-menu CSV import/export workflows with progress/cancel behavior and possible
      bulk API endpoints if large catalog imports prove slow or freeze the UI.
    - Incident Mongo schema cleanup: review and tighten per-incident collections before the DB
      grows further.
      - Liaison: leave liaison collections alone for now because the module still needs further
        product development.
      - Heavily in-development modules: leave the remaining collections alone for now except to
        avoid adding new duplicate collections or fields.
    - Cloud router (`services/cloud_router/`) forwards request/response and WebSocket bodies over the reverse tunnel as base64-in-JSON, capped at 10MB each direction (`SARAPP_ROUTER_MAX_BODY_BYTES`). Fine for typical form/photo sizes; revisit with a streaming transport if large file uploads/downloads through the router prove too slow. See `docs/archive/design-documents/Instructions/cloud_router_architecture.md`.
    - Mobile photo upload isn't implemented yet (Report Hazard's "Attach Photo" is a placeholder button, no `image_picker` dependency). When it's built, submit one photo per request rather than batching several into one multipart body, to stay clear of the 10MB tunnel cap above.
    - Central master database (`services/cloud_router/master_db/`, embedded `sarapp_central_master` Mongo — see `docs/archive/design-documents/Instructions/cloud_router_architecture.md`):
      - Decide whether the desktop app's built-in offline server (`server/server_manager.py`) should participate
        in central-catalog sync like `services/lan_server/server_manager.py`; if not, update the stale docstring that says
        it is functionally identical to the standalone LAN server.
      - Extend the `master_link` sub-document beyond `incident_personnel` to the other master-resource-backed incident collections (vehicles/equipment/aircraft), once that copying is confirmed to exist.
      - Per-operator accounts/audit trail for the central catalog GUI (MVP is a single shared admin login, same pattern as `services/cloud_server/dashboard.py`).
      - Cloud central catalog GUI follow-up: add purpose-built structured editors for nested/versioned catalogs instead of exposing them through the generic free-text CRUD form. Remaining known case is form families/templates/template versions.
      - Personnel duplicate merge workflow: two servers each creating a new personnel record offline before either syncs produces two distinct central documents. Needs a human-reviewed, operator-approved merge UI comparing multiple fields (name, person_id, org, contact info, etc.) — not an automatic match on any single field.
      - `utils/catalog_cache.py` invalidation for remotely-synced master changes (today it only invalidates after locally-initiated writes).
      - MongoDB change streams as a latency optimization layered on the existing push/outbox/pull relay, only if the ~60s poll interval (or a manual resync) ever actually proves too slow — requires every deployment's MongoDB to run as a replica set, which none do today; see `docs/archive/design-documents/Instructions/realtime_architecture_roadmap.md` ("Server ↔ central sync") for the tradeoff.
      - Organization picker source-of-truth drift: ICS-Mobile-App's profile screen organization
        picker (`ICS-Mobile-App/lib/models/organizations.dart`, `Organizations.bundled`) hardcodes the full CAP
        Great Lakes Region roster (MI/IL/IN/KY/OH/WI wings + squadrons) plus a handful of state-agency/civilian
        entries as its offline-first fallback. Its docstring claims this mirrors an authoritative
        `server/sarapp_db/sarapp_db/org_catalog.py` in this repo, but that file does not exist here (never committed, not
        in any worktree/stash) — the desktop app has no equivalent seeded organization list at all, and the
        central master catalog's `organizations` collection starts empty. A CSV derived from the Dart list
        (`data/master_catalog_seed/organizations_glr_seed.csv`) exists to seed the catalog via
        `/central-master/gui/organizations/import`, but until that's uploaded and both clients are pointed at the
        synced catalog instead of (or in addition to) their own bundled/hardcoded copies, desktop and mobile can
        disagree about what organizations exist. Needs: (1) someone to actually upload the seed CSV to a real
        central-master instance, (2) a decision on whether `org_catalog.py` should be created in this repo as a
        real shared source (as the Dart docstring assumes) or whether the mobile app's bundled list should instead
        be treated as the one hand-maintained copy with desktop reading from the synced catalog only, (3) the
        desktop app currently has no "Organizations" picker backed by this same roster at all outside the admin
        Units & Organizations panel — confirm whether any desktop UI needs one before building it.
      - Master facilities catalog: cloud-catalog side done 2026-10-16 — `MasterCollections.FACILITIES`
        + `BaseRepository` router (`server/sarapp_db/sarapp_db/api/routers/master_facilities.py`, distinct from
        the per-incident `facilities.py`), with `name`, `facility_type_id` (FK into a managed `MasterCollections.FACILITY_TYPES`
        lookup catalog — mirroring `organizations.py`'s `organization_types`, with its own `facility-types` `CollectionSpec` —
        rather than a free-text type field), `status`, `parent_organization_id` (FK into `organizations`), address/lat/lon,
        geocoded address, contact/manager fields, and notes — field shape mirrored from the per-incident `FacilityPayload`.
        Registered as the `facilities` `CollectionSpec` in `services/cloud_router/master_db/webgui.py` (CSV/XLSX export
        includes both its own `int_id` and the resolved `facility_type_name`/`parent_organization_name`). Each facility
        type carries an admin-defined `field_schema` (JSON list of `{key, label, input_type, value_type}` definitions)
        and facilities store matching values in their own `attributes` dict — edited as raw JSON text in the web GUI for
        now (`_facility_type_form_row`/`_facility_form_row`/`*_payload` in `webgui.py`), seeded with five starter types
        (Airport/Airstrip, Shelter, Staging Area, EOC, Fuel Point — explicitly not Hospitals, which keep their own
        `MasterCollections.HOSPITALS` catalog) via `server/sarapp_db/sarapp_db/migrations/seed_facility_types.py`.
        Still open: a dynamic form that renders real inputs from a facility's type's `field_schema` instead of a raw
        JSON textarea (worth building once this is used enough to justify it), a desktop Edit-menu panel for this
        catalog (no desktop UI reads/writes it yet — only the central-catalog web GUI does), and whether addresses
        entered here/on organizations get geocoded automatically (needs a geocoding service decision — Nominatim/OSM
        vs. a paid provider vs. manual lat/lon entry only, which is all that exists today) or stay manual-only for now;
        see the Aviation Facilities reference-layer backlog item under `[GIS]` for a related, separate read-only
        external dataset that could feed or coexist with this catalog.
      - ICS-Mobile-App light theme: the mobile app is currently always-dark by design
        (`lib/theme/app_theme.dart`'s `AppTheme` — "a deliberate, always-dark look for a single-purpose field ops
        tool", not following the device's light/dark setting). A light palette doesn't exist yet. If a light mode
        is added later, it needs its own legibility/contrast pass (glare in daylight field use is exactly what the
        dark-only decision was protecting against) rather than just inverting the dark colors, and should wire
        into the Settings screen's Appearance section (`ics_mobile_app` repo) alongside the text-size preference
        already there.

**************************************************************************************************************
[GIS]
  - Aviation Facilities reference layer (noted only, no work started). Searchable dataset to add to maps and
    use during search planning (nearest airstrips/heliports/helibases to a PLS or search area). Not
    medical-related and not incident-scoped; it is shared master/reference data.
    - Source: BTS/FAA NTAD "Aviation Facilities" public ArcGIS Feature Service (item id
      88c147b65ced41d4a1ecb8dac2e9e7e4), layer 0:
      https://services.arcgis.com/xOi1kZaI0eWDREZv/ArcGIS/rest/services/NTAD_Aviation_Facilities/FeatureServer/0
      No API key. Supports spatial/where queries (JSON/GeoJSON/PBF, 2000 records max per request).
      Updated every 28 days from the FAA.
    - Leaning toward a local master-collection copy (offline/LAN friendly) with periodic refresh through a
      BaseRepository subclass, a master router (text search, bbox, near-point radius), a new layer in
      `LayerRegistry`, and a third result group in `MapSearchController`. Open questions: facility types to
      include by default, and who triggers the refresh (LAN console vs. schedule).

**************************************************************************************************************
[Logs]
  - Logs need to be able to write to multiple streams at once.  Would like to be able to generate a log for each individual person, but i dont think writing a separate stream is a good idea.  perhaps something that generates from a lookup of everything that person has done?

**************************************************************************************************************
[Web Logistics follow-up]
- Shared request API hardening: enforce terminal/edit locks on item and fulfillment endpoints,
  not just header PATCH; item replacement currently does not advance version or append an
  audit entry, and fulfillment updates lack actor audit attribution. Preserve the existing
  approval/status transition checks. The browser disables terminal edits but cannot enforce
  these constraints for other API callers.
- Browser Logistics: standalone vehicle/aircraft/equipment catalog administration and facility
  geocoding are pending; resource check-in/status workflows and coordinate entry are available.
- Resource Associations, Resource Packages, Team Builder, and team-readiness validation (2026-10-21)
  shipped server-side (new `resource_associations`/`resource_packages` master routers,
  `checkin.py` package-activation endpoints, `resource_validation.py`) and on the desktop client
  only. `apps/web/` and the mobile app have no equivalent UI yet: no Associations section on the
  web personnel/vehicle/aircraft/equipment detail pages, no Resource Packages list/editor, no
  package-aware check-in prompt, no Team Builder, and no readiness/conflict display on the web
  team detail view. The API is fully usable from the web client as-is (same shared FastAPI app);
  this is purely front-end parity work for `apps/web/` (and mobile, lower priority) following the
  per-module pattern in `apps/web/AGENTS.md`.

**************************************************************************************************************
[Forms — server export migration]
- ICS 203 production exports now use the shared server for FEMA/ICS Canada/USCG.
  Migrate the remaining desktop form exports incrementally through their existing
  domain wrappers/export service; verify mappings and publisher variants before
  removing each local renderer. Preserve Mapper Window's local authoring preview.
- Validate ICS 203 against a real incident with staffed organization positions;
  current eligible local incidents have no saved positions. Populated roles and
  continuation pages have fixture coverage. See form_builder_inventory.md for
  unresolved template fields and the binding audit.
**************************************************************************************************************
[New Features]
- Create new initial response module that can handle non SAR activities.  Ex. severe storm response allows for rapid creation and standup of an EOC during the initial response (specifically teams and tasks)