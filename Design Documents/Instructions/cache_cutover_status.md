# IncidentCache and CatalogCache Cutover Status

Snapshot date: 2026-07-07

This file tracks the migration from direct API reads on window open to cache-first UI reads. Treat it as a working checklist, not timeless policy. Re-run code searches before relying on any row for new work.

## Scope

- **IncidentCache** is for active incident-scoped data loaded from `GET /api/incidents/{incident_id}/snapshot` and kept current by the incident WebSocket stream.
- **CatalogCache** is for shared catalog/master/reference data where a short-lived in-memory cache avoids repeated identical API GET calls.
- Writes still go through the API. The cache is a read path and live-update layer, not a direct database access layer.
- Heavy historical collections must stay bounded in memory and use paged/API detail reads for deep history.

## Status Legend

| Status | Meaning |
|---|---|
| Done | Implemented and covered by focused tests or a direct verification pass. |
| Partial | Some reads use cache, but meaningful direct API reads remain. |
| Not started | No confirmed cache-first read path yet. |
| Needs design | Requires an endpoint, data-shape decision, or pagination policy before broad use. |

## Foundation Status

| Area | Status | Notes |
|---|---|---|
| Incident snapshot endpoint | Done | `incident_stream.py` supports bounded snapshots with per-collection limits, heavy collection limits, and memory budget metadata. |
| IncidentCache snapshot load | Done | `utils/incident_cache.py` stores bounded collections, snapshot metadata, and telemetry. |
| IncidentCache live updates | Done | WebSocket events update cached collections and trim heavy collections after create/update events. |
| IncidentCache completeness tracking | Done | `IncidentCache.is_collection_complete(name)` (`utils/incident_cache.py`) tracks whether a collection has ever been truncated by the server snapshot or trimmed client-side after live updates. Lets a per-subset read (e.g. one person's check-in history out of the whole `checkin_history` collection) safely use the cache only when it's provably complete, falling back to a targeted API query otherwise — see `modules/logistics/checkin/repository.py::list_history` for the reference pattern. |
| Snapshot loader | Done | `utils/incident_cache_loader.py` requests bounded snapshots and passes server metadata into IncidentCache. |
| CatalogCache utility | Done | `utils/catalog_cache.py` memoizes catalog/API GET results with TTL and manual invalidation. |
| Cache architecture docs | Done | `database_architecture.md` and `realtime_architecture_roadmap.md` describe cache-first reads and RAM limits. |
| User-visible cache diagnostics | Not started | Need a small admin/dev surface or log command showing active incident cache size, truncation, and stale/disconnected state. |
| Per-window API call inventory | Partial | Task detail was inspected; remaining panels need a systematic pass. |

## IncidentCache Migration Checklist

| Module / Area | Status | Target |
|---|---|---|
| `modules/statusboards` | Done | `resource_status_desk.py` and `team_task_desk.py` are both fully cache-first (the module has no third board file to migrate). `resource_status_desk.py` reads `resource_status`/`teams`/`org_assignments`/`org_positions` from `incident_cache`, falling back to API GETs only when no cache is loaded. `team_task_desk.py` joins `teams`/`tasks`/`incident_personnel`/`incident_profile` straight from `incident_cache` with no API reads at all; its docstring had a stale caveat claiming team/task writes don't broadcast live (`operations.py` predates `BaseRepository`) -- that's no longer true, so the comment was corrected. Also swapped the Resource Status Board's right-click "Open Team" lookup (`modules/logistics/panels/resource_status_board.py`) from a direct `/operations/teams` GET to the cache-backed `taskings.repository.list_all_teams()`. |
| `modules/operations/taskings` task detail | Partial | Task detail (task, teams, task-team links, audit, status logs, narratives), the Planning tab's objective picker (`list_objectives`, cached `incident_objectives`), debriefs (`list_task_debriefs`/`get_debrief`, cached `task_debriefs`), and task comms/incident channels (`list_task_comms`/`list_incident_channels`, via the new `modules/communications/channel_catalog.py` CatalogCache+IncidentCache join -- see communications-pickers row) are cache-first. Remaining direct-API-only reads: `list_task_personnel`/`list_task_vehicles`/`list_task_aircraft` (explicitly deferred pending personnel/vehicle/aircraft module migration) and `list_strategies_for_task` (see work-assignments row). |
| `modules/operations` teams | Done | `get_team` (Team Detail, ICS-211, org chart), the taskings team picker `list_all_teams`, and `get_checked_in_teams`/`get_unchecked_teams` (ICS-211 check-in/disband team lists, filtering cached `teams` by the same `DERIVED_CHECKED_IN_STATUSES` set and `disbanded` flag the server uses) all read the cached `teams` collection first, falling back to their API GET on cache miss/no active incident. Team assignment history covered via taskings' cached `task_teams`/audit reads (embedded in `tasks` docs). |
| `modules/operations` strategy / work assignments | Needs design | Work assignment detail may need a cache-backed repository plus paged/history routes for large supporting logs. |
| `modules/communications` traffic log | Not started | Main recent log views should use cached recent `communications_log`; older history should remain paged/search API. The default log-window query (`CommsLogQuery()`) is currently an *unbounded* full-history API fetch (no limit) -- caching it to "recent N" would be a real, user-visible behavior change (silently hiding older messages), not a safe refactor, so don't cache-cutover the default view without a product decision on bounding it first. Only a caller-supplied bounded `limit`/no-filter query is safe to serve from cache as-is. |
| `modules/communications` quick entry / pickers | Partial | `list_channels()` (`modules/communications/traffic_log/services.py`) is cache-first via the new `modules/communications/channel_catalog.py`: `get_master_channels_by_id()` memoizes `/api/comms/master-channels` through `CatalogCache` (first real CatalogCache consumer -- `ApiMasterRepository.create_channel` calls `invalidate_master_channels()` after writes; PATCH/DELETE master-channel endpoints have no client-side caller yet, so they don't need invalidation wiring until one exists), and `cached_channel_plan()` joins it against IncidentCache's `incident_channels` the same way `communications.py`'s `_map_incident_channel` does server-side. Reused by taskings' `list_task_comms`/`list_incident_channels` (see that row). `list_contact_entities()` still needs the pre-existing `-TEAM-` marker-parsing dead-code quirk fixed before it can be faithfully cached. |
| `modules/logistics` resource status | Partial | Resource Status Board reads `resource_status` (and joined `teams`/`org_assignments`/`org_positions`) via `ResourceStatusDesk`, which is cache-first (see `modules/statusboards` row). Check-in/out surfaces (`modules/logistics/checkin/` roster fetch, `fetch_checkin`, `CheckInPanel.py` list views) beyond per-person history and checked-in/unchecked team lists are not yet reviewed. |
| `modules/logistics` check-in history | Done | `checkin/repository.py::list_history` (per-person history lookup) reads cached `checkin_history` only when `IncidentCache.is_collection_complete("checkin_history")` is true — i.e. nothing has been truncated/trimmed out of the collection yet — and falls back to the server's per-person `/history/{person_record}` query otherwise. This avoids the failure mode where another person's activity crowds a given person's older entries out of the bounded cache. Design pattern reusable for any other heavy per-subset lookup. |
| `modules/facilities` | Done | `ApiFacilitiesRepository.list_facilities`/`get_facility` (`modules/logistics/facilities/repository.py`) read cached `facilities` docs first (filtered/sorted client-side to match the server's query), falling back to their API calls when no cache is loaded; `FacilitiesService` and all its consumers (weather, facility picker, ICS-206) inherit this for free. Writes (`save_facility`/`delete_facility`) still go through the API. The module's only other `api_client` use (`personnel_picker.py` searching `/api/master/personnel`) is master/catalog data, not facilities data -- tracked under the CatalogCache "Personnel master records" row instead. |
| `modules/command` org / objectives / operational periods | Done | `ApiIncidentOrganizationRepository.list_positions`/`list_operational_units`/`list_assignments`/`list_assignments_for_person`/`list_assignment_history` (`modules/command/incident_organization/repository.py`), taskings' `list_objectives` (cached `incident_objectives`, mirroring `objectives.py`'s `_normalize`), and `OperationalPeriodRepository.list_periods`/`get_period`/`get_active_period` (`modules/planning/operational_periods/repository.py`, cached `operational_periods`) all read cache-first, falling back to their API GETs when no cache is loaded. Note `objectives.py`'s list endpoint supports `include_deleted=True` which the generic IncidentCache snapshot can never serve (deleted docs are always excluded) -- fine for the current picker use case, but a real gap if anything ever needs deleted objectives from cache. Writes (create/update/clone/set-active) still go through the API. |
| `modules/planning` IAP | Needs design | IAP packages/forms may be too large for always-on full caching; cache summaries and fetch large form payloads on demand. |
| `modules/safety` | Partial | `services.py`'s `list_safety_reports`/`list_medical_incidents`/`list_triage_entries`/`list_hazard_zones`/`list_iwi_reports`/`get_iwi_report` now read cached `safety_reports`/`medical_incidents`/`triage_entries`/`hazard_zones`/`iwi_reports` first (filters for severity/flagged/date-range/text-search/status replicated client-side), falling back to their API GETs when no cache is loaded. CAP ORM forms/hazards workflow (`modules/safety/orm/`) and ICS-206/ICS-208 builders are untouched — not yet reviewed. |
| `modules/intel` | Needs design | Intel logs/timelines are potentially heavy; use bounded recent cache plus paged/search routes. |
| `modules/public_information` | Needs design | Generated docs and revisions should not be fully cached by default; cache summary rows and fetch document payloads on demand. |
| `modules/finance` | Done | `services.py`'s fuel price profiles, forecasts, fuel forecast lines, funding sources, expenses, attachments, and approvals all read cached `finance_*` collections first (filters/sort replicated client-side), falling back to API GETs when no cache is loaded. `get_dashboard_snapshot`/`get_fuel_report`/`list_pending_approvals` (server-side Python aggregations) are also reproduced client-side over the same cached collections instead of calling the aggregation endpoints. Writes still go through the API. |
| `modules/gis` | Needs design | Spatial DB remains a separate architecture path; do not assume full GIS feature caching without a specific plan. |
| `modules/referencelibrary` | Needs design | Reference documents and binary/export payloads should not be cached wholesale. Cache metadata only. |

## CatalogCache Migration Checklist

| Catalog / Picker Area | Status | Target |
|---|---|---|
| Resource types | Done | `ApiResourceTypeRepository` (`modules/admin/resource_types/data/resource_type_repository.py`) caches `list_resource_types` (no-search default view only -- the library window's search box is live/debounced, so a `search_text` query bypasses the cache), `get_resource_type`, and `list_capabilities` via `CatalogCache`, invalidating on every write (`save_resource_type`, `replace_components`, `clone_resource_type`, `(de)activate_resource_type`, `save_capability`, `(de)activate_capability`, `set_resource_type_capabilities`, `replace_aliases`, `replace_fema_mappings`). `search_resource_types` (true typeahead) stays uncached, same as the master-radio-channel picker precedent. |
| Hazard types | Done | `ApiHazardTypeRepository` and `ApiSafetyTemplateRepository` (`modules/admin/hazard_types/data/hazard_type_repository.py`, same file) cache their no-search default list view and single-detail fetch via `CatalogCache` (`list_hazard_types`/`get_hazard_type`, `list_templates`/`get_template`), same pattern as Resource types: live/debounced `search_text` queries bypass the cache, and every write path invalidates its catalog namespace. |
| Organizations / units | Done | `UnitsOrganizationsRepository` (`modules/personnel/units_organizations/models/repository.py`) caches `list_organization_types`, `list_rank_structures`, `list_organizations`, `get_organization`, and `list_ranks` (keyed per `rank_structure_id`) via `CatalogCache` -- no live-search UI here, so every list call is memoized (not just a no-search default view). Every write path (org type, rank structure, ranks, organization CRUD, rank-structure override) invalidates its namespace; `replace_ranks`'s internal read-before-delete-and-recreate stays a direct uncached API call by design. |
| Personnel master records | Needs design | Avoid caching full large rosters unbounded; prefer search or bounded active subsets. |
| Vehicles / aircraft / equipment master records | Needs design | Cache small lookup lists and active subsets; use search/paged APIs for large master catalogs. |
| Certifications / qualifications | Not started | Cache shared lookup lists used in personnel and resource dialogs. |
| Radio channels / comm presets | Done | `modules/communications/channel_catalog.py` caches the master radio channel catalog (`get_master_channels_by_id`, via `CatalogCache`, `ApiMasterRepository.create_channel` invalidates on write) and joins it against IncidentCache's `incident_channels` (`cached_channel_plan`). Used by the comms quick-entry channel picker and taskings' task-comms/incident-channels reads. |
| Task / team / strategy templates | Not started | Cache template lists used to create incident records, with invalidation after admin edits. |
| Operational period templates | Not started | Cache shared template/reference lists where they are not incident-specific. |

## Direct API Read Reduction Checklist

| Area | Status | Notes |
|---|---|---|
| Window-open detail loads | Partial | Task detail was optimized. Repeat for team, work assignment, facility, resource, comms detail, and command detail windows. |
| Repeated picker loads | Not started | Replace repeated identical GETs with CatalogCache and explicit invalidation after writes. |
| Repeated count/card loads | Not started | Move count/card calculations to IncidentCache selectors where snapshot data is already present. |
| Polling timers | Not started | Audit timers that reload data already covered by WebSocket-backed IncidentCache updates. |
| Large table history views | Needs design | Keep recent cached rows for fast open, then page/search older rows from API. |

## Acceptance Criteria For Each Migrated Surface

- Opening the window does not perform repeated full-list API GETs for incident data already present in IncidentCache.
- The UI still writes through existing API repositories or clients.
- Cache-backed reads handle missing/truncated collections by falling back to a targeted API detail/page call, not an unbounded full-list load.
- Heavy collections show recent data quickly and fetch older/deeper data on demand.
- CatalogCache entries are invalidated or refreshed after admin/catalog writes.
- Focused tests cover the cache read path, fallback path, and invalidation path when practical.

## Useful Search Starting Points

```bash
rg -n "api_get|api_request|requests\\.|httpx|urllib|QNetwork" modules utils panels ui bridge
rg -n "incident_cache|catalog_cache" modules utils panels ui bridge
rg -n "QTimer|timer|setInterval|refresh|reload" modules utils panels ui bridge
```

Re-run before trusting this checklist.
