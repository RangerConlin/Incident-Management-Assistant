# API And Router Rules

## Core Rules
- The shared FastAPI app entry point is `data/db/sarapp_db/api/app.py`. The LAN server, cloud server, and built-in offline server all serve that app.
- Incident/master Mongo-data routers live under `data/db/sarapp_db/api/routers/`.
- Equivalent router changes must be mirrored under `cloud_server/sarapp_db/api/routers/` so the two copies do not drift.
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
