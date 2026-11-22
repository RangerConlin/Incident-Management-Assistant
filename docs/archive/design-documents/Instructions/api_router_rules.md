# API And Router Rules

## ICS-214 Activity Entries

- `/api/incidents/{incident_id}/ics214/entries` is the canonical operational logging surface. There are no stored streams and no stream CRUD endpoints.
- Entry writes go through `Ics214EntriesRepository`. Each entry is an independent immutable document; never add update or hard-delete entry endpoints.
- Immutable built-in logs use stable `log_keys` defined in
  `sarapp_db.ics_reference`. They exist independently of incident organization
  records and cannot be edited or archived through log-definition endpoints.
- People, teams, tasks, organizational units, facilities, resources, and
  agencies use typed ID arrays as optional secondary associations and filters;
  they do not define the identity of a built-in log.
- `incident_wide=true` is intentional overall-incident scope. Empty `log_keys`
  and association arrays with `incident_wide=false` derive the unassigned state.
- Corrections void the original and create a new entry linked by `corrects_entry_id`.
- `/ics214/log-definitions` returns immutable built-in definitions plus custom
  saved filters. Custom definitions store reusable filters and export headers
  only; they do not own or duplicate activity entries.
- ICS-214 operational entries and technical audit records are separate systems.

## Core Rules
- The shared FastAPI app entry point is `server/sarapp_db/sarapp_db/api/app.py`. The LAN server, built-in offline server, and hosted cloud server all serve that app. The hosted cloud server (`cloud_server/`) wraps the shared app with connect-code path handling and dashboard routes; it must not fork or duplicate incident/master routers.
- Incident/master Mongo-data routers live under `server/sarapp_db/sarapp_db/api/routers/`.
- Router changes do **not** need to be mirrored anywhere. `cloud_server/` imports the shared app and should only contain hosted packaging, dashboard, and deployment-specific code.
- A small number of modules keep self-contained `modules/<module>/api.py` routers for module-local, non-Mongo endpoints such as `forms_creator` and `initialresponse`.
- Test router changes with FastAPI app inclusion where practical.

## Repository Rule
- All incident-database writes must go through a `sarapp_db.mongo.repository.BaseRepository` subclass.
- Routers must not call `insert_one`, `update_one`, `delete_one`, or similar write methods directly on a raw collection handle.
- `BaseRepository` is responsible for stamping timestamps/ids and broadcasting change events to `IncidentCache` WebSocket clients.

## UI And Repository Boundary
- UI code must use `utils/api_client.py` and repository/service abstractions rather than database handles.
- For client-side cutovers, append an `Api*Repository` class to the existing repository file and keep the SQLite repository in place until that module is fully cut over.
- UI/service code should default to the API repository once the cutover is complete.

## Headless form exports

The shared form-export API is the only production binding and rendering
pipeline. Clients must not resolve mappings, assemble bound form data, or fill
PDFs locally. Desktop, web, and mobile submit canonical source identifiers to
`POST /api/incidents/{incident_id}/form-exports` and consume the returned PDF.
Local desktop tools may inspect templates and preview mappings while authoring,
but must never serve as a runtime fallback for an unregistered server form.

`POST /api/incidents/{incident_id}/form-exports` renders saved incident records via
`sarapp_db.form_exports`. The full app mounts it; master-only servers do not. Keep
export reads in repository subclasses without calling legacy runtime ID-repair helpers,
and do not import desktop modules, Qt, app state or local SQLite into the server.
The allowlisted catalog binds each form to its source type and explicit publishing set.
Missing records/periods are errors; do not silently substitute another incident or period.
Exports are read-only downloads, not approvals or stored form/attachment records.

ICS 203 is the first desktop export migrated to this endpoint. It requires an
explicit operational-period ID and supports explicit `form_set_id` values `fema`,
`ics_canada`, and `uscg`; unsupported sets are errors, with no legacy renderer
fallback. The selected period labels the current saved organization, not a
historical organization snapshot. Read canonical `incident_org` embedded `primary`,
`deputies`, and `staff_assistants` arrays, excluding ended assignments; resolve
referenced master personnel through repositories. Keep the established binding
paths and per-set mappings. Desktop widgets call the domain wrapper
`modules/command/incident_organization/export_service.py`, which uses the existing
export registry/service and the binary API client. Rendering runs off the UI thread.
Leave signature widgets and documented ambiguous fields blank. Continuations keep
each branch in its original slot while its divisions continue on subsequent sheets.

Templates are bundled within `sarapp_db/form_exports/assets` for standalone/container and
wheel installs. They are byte copies of the established desktop form assets; run
`python tools/scripts/sync_server_form_templates.py` after source template changes, and
`--check` for drift. Shared server packaging includes these files. PDF dependencies are
pypdf >= 6 and reportlab >= 4. The web binary-download path stays in `src/api/client.ts`,
uses the configured connection target/JWT, and reports non-PDF/error responses.

Add mappings only against verified field names from the actual PDF. Preserve interactive
field trees/appearances, leave signatures blank, paginate repeated rows, and retain
continued text in the appended source annex. Tests must reopen output and compare logical
field values with page widgets, in addition to visual checks.
ICS 203 also bundles the authoritative JSON mappings; sync/check both JSON and PDF
assets after changes. Its narrow original fields may fit text down to 6 points;
longer values still receive an explicit continuation marker and lossless annex.

## Checklists (program-wide, Phase 4A)

- `api/routers/checklist_templates.py` (master catalog, `/api/checklist-templates`)
  and `api/routers/checklists.py` (instances) are shared infrastructure, not
  owned by the Planned Events Toolkit or any other feature module — see
  `mongodb_schema_decisions.md`'s "Checklists" entry for the full data model.
- `checklists.py` implements every operation once as a `_*_impl(incident_id:
  Optional[str], ...)` function, then exposes it under two thin route
  families that share that implementation: `/api/incidents/{incident_id}/checklists...`
  (incident-scoped) and `/api/checklists...` (standalone, no incident,
  stored in `sarapp_master` instead of a per-incident database). This is the
  precedent to copy for any future collection that needs to support both an
  incident-scoped and a standalone instance of the same resource without
  duplicating validation/business logic.
- `BaseRepository.apply_update` takes an optional `array_filters` kwarg,
  passed straight through to PyMongo, for a targeted update on one element
  of a nested array (e.g. one item inside one section of a checklist)
  without a read-modify-write race against a concurrent update to a
  different element of the same array. Prefer this over reading the whole
  document, mutating it in Python, and writing the whole field back,
  whenever a write only needs to touch one element of a nested array.

## Checklists — lifecycle & ICS-214 integration (Phase 4B)

- The Phase 4A generic `PATCH .../checklists/{id}/status` is gone. Status
  only changes through `POST .../complete`, `.../reopen`, `.../archive` —
  each revalidates and atomically claims its own transition
  (`checklists._claim_transition`); there is no endpoint that can set an
  arbitrary status directly.
- `checklists.py` is the one caller that writes ICS-214 entries from
  outside `ics214.py` itself (besides `ics214.py`'s own internal "mobile"
  routes) — it imports `ics214._insert_entry`/`EntryCreate`/`SourceRecord`
  directly rather than going through HTTP, matching the existing
  intra-process-import convention for cross-module reuse in this codebase
  (same as `operations.py` importing `gar_templates.score_selections`).
  Any future module that needs to log a significant lifecycle event should
  follow the same pattern: import `_insert_entry`/`EntryCreate` directly
  and supply a deterministic `idempotency_hash`, never build a parallel
  logging endpoint.
- See `mongodb_schema_decisions.md`'s "Checklists — lifecycle & ICS-214
  integration" entry for the full stream-resolution order, idempotency
  scheme, and pending-entry recovery mechanism (`POST .../ics214/retry`).

## Checklists — Planned Events associations (Phase 4D)

- `POST .../checklists/{id}/links` / `.../links/remove` add/remove one
  `{record_type, record_id}` association without touching anything else
  on the checklist. Both mirrored for the incident-scoped and standalone
  URL families, matching the rest of `checklists.py`'s dual-family
  convention (standalone's add always 400s — see
  `mongodb_schema_decisions.md`'s Phase 4D entry).
- `checklists.propagate_link_to_promoted_task` is a plain importable
  function other routers can call after creating a record that should
  inherit a checklist's existing links — `plannedtoolkit.py`'s Assignment
  promotion endpoint is the first caller, imported lazily inside the
  function body (the same intra-process cross-router import convention
  `ics214.py`'s `_insert_entry` and `gar_templates.score_selections`
  already use), wrapped in try/except so a propagation failure never
  blocks the primary action it's attached to.
