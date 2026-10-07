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

**************************************************************************************************************
[Planning]
Planning Dashboard

Operational Period Manager

Demobilization Planner

Meeting Planner

Individual Meeting Detail Windows

Situation Report
  - Move to under the command menu
  
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
  for the module's own follow-ups: lightning data deferred (no reliable free API); runway crosswind
  data now comes from a live NOAA AWC airport lookup (services/runway_api.py) queried once at
  station-creation time and cached, no bundled CSV needed; NWS location-code hint caching
  (location_codes.py) isn't wired back into the new WeatherManager yet (forecast/HWO still work,
  just without the caching speedup).
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

**************************************************************************************************************
[Liaison]
Redesigned around the LOFR's actual job — controlling what information flows between incident
staff and external customers — not generic agency CRUD. Dashboard (modules/liaison/liaison_window.py)
follows the Public Information module's structure (button bar + overview + linked windows), now
bold/saturated-colored via new LIAISON_AGENCY_STATUS/LIAISON_PRIORITY/LIAISON_REPORT_STATE
palettes in styles/profiles/{dark,light}.py. Three sections:
  - Agency Directory — unchanged CRUD board, re-themed.
  - Reporting Board (modules/liaison/panels/reporting_board.py, new liaison_reporting_digests
    collection) — LOFR pulls a live Objective/Task status, curates a customer-facing summary,
    gates it behind a Ready to Report toggle before it's shareable.
  - Customer Requests & Feedback (modules/liaison/panels/customer_board.py) — incoming customer
    requests can be converted directly into a real Objective or Task (origin_module/origin_id
    back-link added to both schemas), plus Resource Offers and Feedback tabs.
  - Remaining gap: Agency Detail dialog's Contacts / Restrictions / Agreements tabs are
    read-only (backend supports Contacts CRUD; Restrictions/Agreements have no create UI at
    all) — add "add" dialogs for these if the LNO workflow needs them tracked.
**************************************************************************************************************
[PIO]
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
    - Cloud router (`cloud_server/router/`) forwards request/response and WebSocket bodies over the reverse tunnel as base64-in-JSON, capped at 10MB each direction (`SARAPP_ROUTER_MAX_BODY_BYTES`). Fine for typical form/photo sizes; revisit with a streaming transport if large file uploads/downloads through the router prove too slow. See `Design Documents/Instructions/cloud_router_architecture.md`.
    - Mobile photo upload isn't implemented yet (Report Hazard's "Attach Photo" is a placeholder button, no `image_picker` dependency). When it's built, submit one photo per request rather than batching several into one multipart body, to stay clear of the 10MB tunnel cap above.
    - Central master database (`cloud_router/master_db/`, embedded `sarapp_central_master` Mongo — see `Design Documents/Instructions/cloud_router_architecture.md`):
      - Generalize the web GUI (`cloud_router/master_db/webgui.py`) and the sync relay (`data/db/sarapp_db/sync/`, `sync.config.SYNCABLE_MASTER_COLLECTIONS`) from `personnel`/`equipment` to the rest of the master inventory, each with a matching desktop "Resync" button. No collection-specific sync-relay code needed — confirmed when `equipment` was added (just a config entry + a test). Decided 2026-10-07 (see `Design Documents/Instructions/mongodb_schema_decisions.md` "Personnel: central-vs-local record ids" and its terminology section for the local-catalog/central-catalog vocabulary this plan uses): every collection below needs one of two treatments, done one collection at a time like `personnel`/`equipment` were:
        - **Dual-key treatment** (apply the same `person_record`/`person_record_master` pattern via the now-generalized `dual_key_field()` helper in `data/db/sarapp_db/mongo/int_id.py` — local catalogs keep minting their own local key, the central catalog mints `<thing>_record_master` either immediately on a central-direct create or on first sync of an offline-created record, via `sync.py`'s `_DUAL_KEY_MASTER_FIELDS`):
          - Done 2026-10-07: `equipment`, `vehicles`, `aircraft` (added to `SYNCABLE_MASTER_COLLECTIONS` alongside `personnel`; `cloud_router/master_db/webgui.py`'s `equipment`/`vehicles` specs updated to key off the `_master` field).
          - Done 2026-10-07: `hazard_types`, `gar_templates`, `canned_comm_entries`, `hospitals` (local field `id`, master field `id_master`); `objective_templates`, `strategy_templates` (local field `int_id`, master field `int_id_master`); `radio_channels` (local field `channel_id`, master field `channel_id_master`, in `communications.py`'s `master_router` only — the incident-scoped comms/teams/personnel-suggestion endpoints in that same file are untouched); `safety_analysis_templates` (local field `template_id`, master field `template_id_master`). All added to `SYNCABLE_MASTER_COLLECTIONS` and `sync.py`'s `_DUAL_KEY_MASTER_FIELDS`, and to `rename_dual_key_fields_to_master.py`.
          - Deliberately **not** dual-keyed: `meeting_templates`. Its three `master_router` endpoints (`meetings.py`) are keyed by a user-chosen `slug` with upsert (PUT) semantics, not an auto-incrementing id — two offline servers both creating a "safety-briefing" template is a content-naming collision, not an id-minting race, so there's nothing for a dual key to solve here.
        - **Lockdown treatment** (central-authoritative; local catalogs reject create/update/delete with a 403 via a `_require_central()` guard, reads untouched):
          - Done 2026-10-07: `organizations`, `organization_types`, `rank_structures`, `ranks`, `organization_rank_structure_overrides` (all in `organizations.py`); `resource_types`, `resource_capabilities` (`resource_types.py`); `form_families`, `form_templates`, `form_template_versions` (`forms.py`, `master_router` only — incident form instances on `incident_router` are untouched). Covered by `data/db/sarapp_db/api/routers/tests/test_lockdown_guards.py`.
          - Still needed, and a bigger lift than the others because there's no central router to guard yet: `task_types`/`team_types` (currently only `lookup_types.py`, mounted in `mode="full"` only — needs to actually be mounted on the central catalog too before a write-guard means anything) and `certification_types`/`certification_tags` (no API router exists anywhere yet, local or central — these would need new endpoints, not just a guard on existing ones). `incident_types` has no write endpoint at all today (read-only with hardcoded fallback defaults in `lookup_types.py`), so it's already effectively locked down; only the two audit logs (`organization_audit_log`, `rank_structure_audit_log`) need no separate guard since they're written only from inside the now-guarded `organizations.py` endpoints.
          - Known tradeoff accepted by this treatment: a LAN/cloud server with no central connectivity yet has no way to create a brand-new organization/rank/resource type/form template locally anymore (previously it could, just disconnected from central). Worth flagging if initial server setup/seeding ever depends on local creation before a server has ever reached central.
        - `personnel_certifications` needs neither — it's legacy and rides along with `personnel` entirely (see the `legacycode.md` entry added 2026-10-07).
        - Not yet placed: `users`, `user_sessions`, `user_profiles`, `role_templates`, `client_connections`, `push_tokens` stay local-catalog-only by design (their routers only mount in `mode="full"`, never `master_only"`) — out of scope for this migration, not an oversight.
        - Fixed 2026-10-07: `resource_types.py`, `strategy_templates.py`, and `objective_templates.py` each hardcoded the literal database name `"sarapp_master"` instead of calling `get_master_db()` — on the central catalog they'd have silently read/written a stray, wrong database instead of the real central catalog. All three now call `get_master_db()` like every other master router.
      - Extend the `master_link` sub-document beyond `incident_personnel` to the other master-resource-backed incident collections (vehicles/equipment/aircraft), once that copying is confirmed to exist.
      - Per-operator accounts/audit trail for the central catalog GUI (MVP is a single shared admin login, same pattern as `cloud_server/dashboard.py`).
      - Personnel duplicate merge workflow: two servers each creating a new personnel record offline before either syncs produces two distinct central documents (see `Design Documents/Instructions/mongodb_schema_decisions.md` "Personnel: central-vs-local record ids"). Needs a human-reviewed, operator-approved merge UI comparing multiple fields (name, person_id, org, contact info, etc.) — not an automatic match on any single field. Not started.
      - Automatic incident→master write-back (MVP treats this as an explicit, operator-initiated action, not automatic).
      - `utils/catalog_cache.py` invalidation for remotely-synced master changes (today it only invalidates after locally-initiated writes).
      - MongoDB change streams as a latency optimization layered on the existing push/outbox/pull relay, only if the ~60s poll interval (or a manual resync) ever actually proves too slow — requires every deployment's MongoDB to run as a replica set, which none do today; see `Design Documents/Instructions/realtime_architecture_roadmap.md` ("Server ↔ central sync") for the tradeoff.
      - Organization picker source-of-truth drift (found 2026-10-07): ICS-Mobile-App's profile screen organization
        picker (`ICS-Mobile-App/lib/models/organizations.dart`, `Organizations.bundled`) hardcodes the full CAP
        Great Lakes Region roster (MI/IL/IN/KY/OH/WI wings + squadrons) plus a handful of state-agency/civilian
        entries as its offline-first fallback. Its docstring claims this mirrors an authoritative
        `data/db/sarapp_db/org_catalog.py` in this repo, but that file does not exist here (never committed, not
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
      - Master facilities catalog (requested 2026-10-07): a reusable, agency-wide directory of known physical
        locations (airports/airstrips, hospitals, fairgrounds, EOCs, staging areas, CAP squadron buildings, etc.)
        with a geocoded address, distinct from the per-incident `modules/logistics/facilities/` module (ICP,
        staging, bases, etc. scoped to one incident) and from `organizations` (who, not where — organizations
        picked up `address`/`latitude`/`longitude` fields on 2026-10-07, so this catalog and that field addition
        overlap and should be designed together rather than duplicating address storage). Candidate shape:
        name, facility type, address, lat/lon, contact info, notes, maybe a parent organization link. Follow the
        same pattern as the `personnel`/`equipment`/`vehicles`/`organizations` master collections (BaseRepository
        + router under `data/db/sarapp_db/api/routers/`, a `CollectionSpec` entry in
        `cloud_router/master_db/webgui.py`, and a desktop Edit-menu panel). Open question: whether addresses
        entered here/on organizations get geocoded automatically (needs a geocoding service decision — Nominatim/
        OSM vs. a paid provider vs. manual lat/lon entry only, which is all that exists today) or stay manual-only
        for now; see the Aviation Facilities reference-layer backlog item under `[GIS]` for a related, separate
        read-only external dataset that could feed or coexist with this catalog.

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
