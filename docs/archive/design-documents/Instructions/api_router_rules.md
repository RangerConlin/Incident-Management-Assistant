# API And Router Rules

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
