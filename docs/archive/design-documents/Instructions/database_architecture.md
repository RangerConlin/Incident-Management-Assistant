# Database Architecture

## Persistence Architecture
- **MongoDB** is the active backend for cut-over modules. Three logical databases:
  - `sarapp_system` for server/app configuration
  - `sarapp_master` for agency-wide reference data such as personnel, vehicles, equipment, and templates
  - `sarapp_incident_<id>` for incident-scoped data, audit trail, and forms
- **SQLite** files in `data/` remain for modules not yet cut over, including `data/master.db` and `data/incidents/<id>.db`.
- Key MongoDB files in `server/sarapp_db/sarapp_db/mongo/`:
  - `collection_names.py` for collection constants
  - `indexes.py` for idempotent index creation
  - `database_manager.py` for `get_system_db()`, `get_master_db()`, and `get_incident_db(id)`
- All UI code goes through `utils/api_client.py` (`httpx.Client` singleton). Do not add direct DB access from the UI layer.
- Active incident UI reads should prefer `utils.incident_cache.incident_cache` when the needed collection is available there. The cache is loaded from a bounded `/api/incidents/{incident_id}/snapshot` response and kept current by WebSocket events. Do not bypass API writes; write through routers/repositories and let broadcasts update the cache.
- Stable master/global lookup reads should use `utils.catalog_cache.catalog_cache` where practical, with explicit invalidation after catalog writes.
- Do not cache large binary/export content in RAM by default. Heavy/history collections should be recent-only, capped, or paged.

## Incident Export/Import
- `server/sarapp_db/sarapp_db/export_import/` builds and restores a universal, portable
  incident package: a zip of `manifest.json` + one `collections/<name>.json`
  per non-empty `IncidentCollections.*` collection (dumped with
  `bson.json_util`) + every GridFS attachment blob under `attachments/`.
- Exposed via `server/sarapp_db/sarapp_db/api/routers/incident_transfer.py`:
  `GET /api/incidents/{incident_id}/export` and `POST /api/incidents/import`.
- Import always creates a **brand-new incident** (never merges into an
  existing one) via the shared `create_incident_records()` helper in
  `ic_overview.py`. It also rewrites any `incident_id` field embedded inside
  restored documents (and GridFS metadata) to the new incident, and remaps
  `attachments.gridfs_file_id` to the re-uploaded file's new id — both ids
  change on import even though document `_id`s are preserved as-is.
- Bulk restores go through `BaseRepository.bulk_insert()` (no per-document
  broadcast, unlike `insert_one`) rather than a raw `insert_many` on the
  collection, keeping every incident-database write funneled through a
  `BaseRepository` subclass per the hard rule.
- Known gap: `finance_attachments` documents store a local filesystem
  `file_path` rather than a GridFS id (see `docs/archive/design-documents/legacycode.md`),
  so those files don't travel with an export — only the metadata row does.

## Templates And Config
- Templates/forms live in `data/forms`, `data/templates`, and `profiles/`.
- Theme tokens live in `utils.theme_manager` and `styles/palette.py`.
- UI customization data lives in `modules/ui_customization` repositories/models.

## Authentication
- `server/sarapp_db/sarapp_db/api/routers/auth_sessions.py` (`/api/auth`) owns user identity and session/presence state in `sarapp_master.users`/`user_sessions`. `/lookup`, `/register`, `/profile`, and `/sessions*` are identity-only — no password — and back desktop's local/offline operator context.
- `/password/set` and `/login` add a real password (salted PBKDF2, `_hash_password`) and a JWT (`SARAPP_JWT_SECRET` env var; falls back to a random per-process secret, so tokens stop validating across a restart if that var is unset) on top of the same `users` records. `/password/set` only works once per account by design — there is no reset/change flow yet.
- This backs the web client's (`web_client/`) login only, and **no router enforces it** — not a gap awaiting a narrow fix, a deliberate reversal. A tunnel-scoped enforcement design (require the JWT only for requests arrived via `cloud_router`'s public tunnel, reusing `app.py`'s `_TUNNEL_CLIENT_IP_HEADER`/`_client_address()` signal) was designed and then dropped before any code landed: the LAN tunnel is currently not working, so real desktop/mobile traffic already arrives looking tunnel-sourced, meaning that design would have required auth on essentially all production traffic immediately, with no client able to send a token — an outage, not a security improvement. See the `web_client` entry under `[Tech Debt / Infrastructure]` in `backlog.md` for what any future attempt at this needs to account for.

## Active Incident Number
- Source of truth: `utils/state.py` via `AppState`.
- Read in UI/bridges with `AppState.get_active_incident()`.
- Prefer string IDs for persistence via `utils.incident_context.get_active_incident_id()`.
- DB path helper: `utils.incident_context.get_active_incident_db_path()` raises if there is no active incident.
- Set/update selection with `AppState.set_active_incident(<incident_number>)`. This also synchronizes `incident_context` and emits `app_signals.incidentChanged` (`str`).
- Listen to `utils.app_signals.app_signals.incidentChanged` to refresh bound views.
- FastAPI/services should accept `incident_id` explicitly where practical so routing stays obvious and testable.
- Tests can set `AppState.set_active_incident("TEST-123")` or `incident_context.set_active_incident("TEST-123")`; use `CHECKIN_DATA_DIR` for sandboxed paths.

## Resource Associations And Resource Packages (sarapp_master)
- `MasterCollections.RESOURCE_ASSOCIATIONS` (`resource_associations.py` router,
  `server/sarapp_db/sarapp_db/mongo/resource_kinds.py` helper) holds
  **standing, non-incident-specific** relationships between two individual
  master resources (personnel/vehicle/aircraft/equipment) -- a radio
  assigned to a person, equipment carried onboard a vehicle. Each document
  has `source`/`target` endpoints (`{resource_type, resource_id}`), a free-text
  `association_type` (no enum -- new relationship kinds need no schema
  change), optional `owning_organization`/`effective_start`/`effective_end`,
  `notes`, and `active`. Duplicate (source, target, type) pairs and
  dependency cycles are rejected server-side (`find_path` graph search);
  invalid resource references are rejected with 404. **Nothing in the
  incident-team code path (operations.py teams, checkin.py) may write to
  this collection** -- changing an incident team's composition must never
  alter a standing association.
- `resource_kinds.py`'s `RESOURCE_KIND_FIELDS` is the one place that maps a
  `resource_type` string to its master collection and dual-key record field
  (reusing `int_id.dual_key_field`, the same local-vs-central pattern every
  other master collection already follows). Any new feature that needs to
  reference "an individual master resource" generically (packages, check-in
  integration, validation) should resolve through this module rather than
  re-deriving the mapping.
- Desktop UI: `modules/admin/resource_associations/` (models, API-backed
  repository, a generic cross-kind `ResourcePickerDialog`, and an embeddable
  `AssociationsPanel`). The panel is wired into Personnel
  (`ui/personnel/ui_personnel.py`), Vehicle (`vehicle_edit_window.py`),
  Aircraft (`aircraft_inventory_window.py`'s `AircraftDetailPane`), and
  Equipment (`equipment_edit_panel.py`) detail dialogs. Each of those modules
  calls `associations_panel.register_open_handler(<kind>, <opener>)` at
  import time so "Open Associated Resource" can jump to any kind's own
  detail window without the panel importing all four modules up front.
- `MasterCollections.RESOURCE_PACKAGES` (`resource_packages.py` router) holds
  reusable collections of personnel/vehicles/aircraft/equipment that
  routinely respond together (a CAP ground team, a fire engine company) --
  a standing roster definition, never an incident team. Membership mixes,
  per resource reference, `membership: fixed | preferred | optional`, plus
  package-level `required_positions` (role/qualification, no person named)
  and `minimum_quantities` (e.g. "4 qualified personnel"). A package is
  always saveable incomplete/understaffed -- the router never requires full
  staffing to create or save one, and resource-existence/duplicate
  validation only runs against whatever membership *is* present.
  `GET /api/resource-packages/for-resource/{type}/{id}` lists every active
  package naming a given resource anywhere in its membership, for Stage 4's
  check-in integration. A resource may legitimately belong to several
  packages' standing membership at once -- that is never itself a conflict
  (see the Stage 6 conflict-prevention note once it lands).
- Desktop: `modules/admin/resource_packages/` (model, API repository, a
  list window, and a tabbed editor window following the Resource Type
  Library editor's convention -- Overview / Personnel / Vehicles / Aircraft
  / Equipment / Requirements). Reuses `resource_associations`' generic
  `ResourcePickerDialog` for membership selection. Reachable from
  Edit -> Resource Packages.

## Check-In / Package Activation Integration (Stage 4)
- `IncidentCollections.PACKAGE_ACTIVATIONS` (`sarapp_incident_<id>.package_activations`,
  `PackageActivationsRepository` in `checkin.py`) records which package was
  activated, which resources were actually used (confirmed/substituted),
  and which expected members were omitted -- one append-only document per
  activation, never a snapshot of the package's standing definition.
- New endpoints on the existing `checkin.py` router (still mounted at
  `/api/incidents/{incident_id}/checkin`):
  - `GET /package-suggestions/{resource_type}/{resource_id}` -- standing
    packages involving a resource that just checked in, each member
    annotated with its current checked-in state.
  - `GET /packages/{package_id}/status` -- the same per-member annotation,
    independent of any triggering resource (used by Team Builder).
  - `POST /packages/{package_id}/activate` -- confirms which members
    arrived (optionally substituted or omitted) and checks in **only**
    those; absent members are never auto-checked-in. Reuses each resource
    kind's own existing idempotent check-in write (`save_checkin` for
    personnel, `incident_resources.check_in_resource` otherwise) so a
    resource already at or past "checked in" status is left untouched
    rather than duplicated or downgraded.
  - `GET /packages/activations` -- activation history for the incident.
- Desktop: `modules/admin/resource_packages/widgets/package_activation_dialog.py`'s
  `offer_package_activation(resource_type, resource_id, parent)` is called
  right after a resource checks in from the two primary check-in surfaces
  (`ics211_window.py`'s full check-in flow and `checkin_window.py`'s Quick
  Check-In). It is a no-op when the resource is in no package or every
  package member is already checked in, and never prompts for, or writes,
  anything beyond what the operator explicitly confirms per row (Confirm
  Arrived / Substitute / Omit / Pending).
