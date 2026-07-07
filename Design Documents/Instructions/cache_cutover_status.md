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
| Snapshot loader | Done | `utils/incident_cache_loader.py` requests bounded snapshots and passes server metadata into IncidentCache. |
| CatalogCache utility | Done | `utils/catalog_cache.py` memoizes catalog/API GET results with TTL and manual invalidation. |
| Cache architecture docs | Done | `database_architecture.md` and `realtime_architecture_roadmap.md` describe cache-first reads and RAM limits. |
| User-visible cache diagnostics | Not started | Need a small admin/dev surface or log command showing active incident cache size, truncation, and stale/disconnected state. |
| Per-window API call inventory | Partial | Task detail was inspected; remaining panels need a systematic pass. |

## IncidentCache Migration Checklist

| Module / Area | Status | Target |
|---|---|---|
| `modules/statusboards` | Partial | Confirm every dashboard/status card reads from IncidentCache where incident-scoped data is already in the snapshot. |
| `modules/operations/taskings` task detail | Partial | Initial task detail now uses cached task, teams, task-team links, audit, status logs, and narratives where available. Continue sweeping list views and related dialogs. |
| `modules/operations` teams | Not started | Team detail, assignment history, and team selectors should read cached `teams`, `task_teams`, `team_status_log`, and related active collections. |
| `modules/operations` strategy / work assignments | Needs design | Work assignment detail may need a cache-backed repository plus paged/history routes for large supporting logs. |
| `modules/communications` traffic log | Not started | Main recent log views should use cached recent `communications_log`; older history should remain paged/search API. |
| `modules/communications` quick entry / pickers | Not started | Common pickers and default lists should prefer CatalogCache or IncidentCache depending on data ownership. |
| `modules/logistics` resource status | Not started | Resource status boards and check-in/out surfaces should read cached `resource_status` for active incident state. |
| `modules/logistics` check-in history | Needs design | `checkin_history` is heavy; keep recent entries in IncidentCache and use paged API for deep history. |
| `modules/facilities` | Not started | Facility lists/detail windows should use cached incident facility data when included in snapshot. |
| `modules/command` org / objectives / operational periods | Not started | Incident org, objectives, and op period readers should move to IncidentCache for open-window speed. |
| `modules/planning` IAP | Needs design | IAP packages/forms may be too large for always-on full caching; cache summaries and fetch large form payloads on demand. |
| `modules/safety` | Not started | Safety boards, hazards, and medical-plan incident data should use cache-first reads where practical. |
| `modules/intel` | Needs design | Intel logs/timelines are potentially heavy; use bounded recent cache plus paged/search routes. |
| `modules/public_information` | Needs design | Generated docs and revisions should not be fully cached by default; cache summary rows and fetch document payloads on demand. |
| `modules/finance` | Not started | Incident finance/admin lists should be checked for repeated open-time GETs and moved to cache-first where safe. |
| `modules/gis` | Needs design | Spatial DB remains a separate architecture path; do not assume full GIS feature caching without a specific plan. |
| `modules/referencelibrary` | Needs design | Reference documents and binary/export payloads should not be cached wholesale. Cache metadata only. |

## CatalogCache Migration Checklist

| Catalog / Picker Area | Status | Target |
|---|---|---|
| Resource types | Not started | Cache shared type lists used by logistics, operations, and assignment dialogs. |
| Hazard types | Not started | Cache shared hazard type lists used by safety/admin surfaces. |
| Organizations / units | Not started | Cache small master lists; use search/paged APIs for very large rosters. |
| Personnel master records | Needs design | Avoid caching full large rosters unbounded; prefer search or bounded active subsets. |
| Vehicles / aircraft / equipment master records | Needs design | Cache small lookup lists and active subsets; use search/paged APIs for large master catalogs. |
| Certifications / qualifications | Not started | Cache shared lookup lists used in personnel and resource dialogs. |
| Radio channels / comm presets | Not started | Cache common communication presets and picker values. |
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
