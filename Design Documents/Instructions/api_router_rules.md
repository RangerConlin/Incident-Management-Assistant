# API And Router Rules

## Core Rules
- The shared FastAPI app entry point is `data/db/sarapp_db/api/app.py`. The LAN server and built-in offline server serve that app. The cloud server (`cloud_server/`) does **not** — it runs a separate, much smaller reverse-tunnel router app (`cloud_server/router/app.py`) that forwards traffic to a LAN server instead of running `sarapp_db` routers itself. See `Design Documents/Instructions/cloud_router_architecture.md`.
- Incident/master Mongo-data routers live under `data/db/sarapp_db/api/routers/`.
- Router changes do **not** need to be mirrored anywhere — `cloud_server/sarapp_db/api/routers/` is unused legacy scaffolding (see `Design Documents/legacycode.md`), not a second copy that needs to stay in sync.
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
