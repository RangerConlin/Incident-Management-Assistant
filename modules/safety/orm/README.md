# Safety Risk Manager Module

The Safety Risk Manager submodule provides a canonical, incident-wide hazard
register scored with the USCG SPE (Severity x Probability x Exposure) method.
It replaces the earlier CAP-style severity/likelihood ORM form workflow. Data
is stored in MongoDB via the shared FastAPI app, in the `hazards` collection
(`IncidentCollections.HAZARDS`).

## Features

* One canonical hazard per incident, linkable to multiple operational periods,
  work assignments, teams, and tasks (not a per-op-period singleton form).
* SPE scoring (`severity(1-5) x probability(1-5) x exposure(1-4)`), computed
  server-side and banded into Slight / Possible / Substantial / High / Very
  High, each with a fixed recommended action.
* Independent initial and residual SPE assessments per hazard.
* Register PDF export.

## Data Storage

Hazards are read/written via `data/db/sarapp_db/api/routers/safety.py`
(`GET/POST /api/incidents/{incident_id}/safety/hazards`,
`GET/PATCH/DELETE .../hazards/{hazard_id}`), backed by
`IncidentCollections.HAZARDS`. This module has no local database or
SQLite storage — `service.py` is a thin REST client.

The old CAP ORM collection set has been retired. CAPF-160 compatibility
endpoints in `safety.py` synthesize the legacy form/hazard view from canonical
`hazards` documents instead of writing separate CAP ORM collections.

## Development

Run the module's tests with:

```bash
pytest modules/safety/orm/tests --import-mode=importlib
```

To view the desktop UI, launch the main application and open **Medical &
Safety → Safety Risk Manager** from the menu. The widget is implemented with
PySide6 widgets and works fully offline against the local API server.
