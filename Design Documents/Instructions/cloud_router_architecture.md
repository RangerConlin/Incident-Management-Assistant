# Cloud Server Hosting Architecture

## Purpose
`cloud_server/` is the VPS/container-hosted SARApp Cloud Server DB. A cloud
server is intentionally treated as a LAN-server-equivalent backend: it serves
the shared FastAPI app from `data/db/sarapp_db/api/app.py`, connects to its
own MongoDB container, and uses the same connect-code URL shape clients
already understand.

`cloud_server/` does **not** replace the stateless reverse-tunnel router —
that router (`cloud_router/`) is still live, required infrastructure.
`cloud_server/` dials *out* to it and registers a connect code exactly like a
LAN server does; the router is what actually owns the public
`/r/<CONNECT_CODE>/...` URL and forwards traffic down whichever tunnel is
registered for that code. The two are independent services with no shared
files or imports — see `cloud_router/README.md` for why its source lived
only in git history for a while (commit `fed5fbcc`) before being restored.

Clients should not need a different workflow for LAN vs cloud. A cloud URL
such as `https://example.org/r/ABCD-1234` must expose the normal `/health`,
`/server-info`, `/api/...`, and WebSocket paths after the `/r/<code>` prefix.

## Container Model
- One Compose project represents one SARApp server.
- Each project has one `app` container and one `mongo` container.
- Each server has its own MongoDB volume and backup volume.
- Multiple cloud servers can run on the same VPS by using different
  `COMPOSE_PROJECT_NAME` and `SARAPP_CONNECT_CODE` values.
- Traefik routes by path prefix: `PathPrefix(/r/<SARAPP_CONNECT_CODE>)`.

## Code Ownership
- Incident/master API routers live only under `data/db/sarapp_db/api/routers/`.
- `cloud_server/` imports the shared app and must not maintain a second router
  tree.
- `cloud_server/` owns hosted deployment concerns: Docker/Traefik packaging,
  connect-code prefix validation/stripping, dashboard routes, and Mongo backup
  import/export.

## Dashboard
Each cloud server exposes its own dashboard at `/r/<code>/dashboard`.
Dashboard accounts are local to that server and configured through environment
variables, not SARApp users. The dashboard provides:

- server status and MongoDB health
- active client connections
- recent API traffic
- backup export
- backup import into new databases
- container update instructions for the VPS operator

## Backup Import/Export
Dashboard backup exports are SARApp Mongo backup ZIP files containing
`metadata.json` plus JSON dumps of `sarapp_system`, `sarapp_master`, and every
`sarapp_incident_*` database. Imports must not overwrite live databases; they
restore into new database names with an operator-supplied suffix.

## Secrets And Configuration
Use environment variables or a Compose `.env` file for deployment settings:

- `SARAPP_CONNECT_CODE`
- `SARAPP_SERVER_NAME`
- `SARAPP_SERVER_ID`
- `SARAPP_MONGO_URI`
- `CLOUD_ADMIN_USERNAME`
- `CLOUD_ADMIN_PASSWORD` or `CLOUD_ADMIN_PASSWORD_SHA256`
- `CLOUD_SESSION_SECRET`

Never hardcode `SARAPP_MONGO_URI`, dashboard passwords, or session secrets.

## Central Master Database (cloud_router, 2026-10)

`cloud_router/` optionally owns its own embedded MongoDB instance and
database — `sarapp_central_master` — holding the authoritative, centralized
agency-wide catalog (personnel, equipment, vehicles, aircraft, hospitals,
certifications, organizations, templates, forms, etc. — the same collections
documented in `master_collection_inventory.md`). This is a deliberate,
confirmed exception to `cloud_router/`'s "no database" rule, made because
every LAN/cloud server previously ran its own fully independent copy of this
catalog (`sarapp_master`) with no single source of truth across the org.

**Relationship to each server's local `sarapp_master`:** `sarapp_master` and
`sarapp_central_master` are schema-identical but are separate databases on
separate MongoDB instances — a LAN/cloud server's local master catalog is not
replaced by the central one; it syncs with it (sync design below, not yet
implemented — see `realtime_architecture_roadmap.md`). The distinct name
exists specifically so a misconfigured `SARAPP_MONGO_URI` can never cause a
server to read/write the wrong one.

**Implementation — reuse, not duplication:** the central database is served
by the *existing* master-catalog routers/schemas in `data/db/sarapp_db/api/
routers/` completely unmodified. `data/db/sarapp_db/api/app.py::create_app()`
takes a `mode` argument: `mode="full"` (the default, used by every LAN/cloud
server and the offline server) mounts every router; `mode="master_only"`
mounts just the master-catalog subset and omits every incident-scoped
router. `cloud_router/master_db/app.py::create_master_app()` calls
`create_app(mode="master_only")` after pointing the process at its own Mongo
instance (`SARAPP_CLOUD_ROUTER_MONGO_URI` → the process's `SARAPP_MONGO_URI`)
and redirecting `get_master_db()` to `sarapp_central_master` instead of
`sarapp_master` via the `SARAPP_MASTER_DB_NAME` environment variable — see
`data/db/sarapp_db/mongo/database_manager.py`. `cloud_router/router/app.py`
mounts the result as a sub-app at `/central-master`, so the central catalog
is reachable at `/central-master/api/master/...`, the same paths every
desktop client already calls over LAN/localhost.

This is optional: leaving `SARAPP_CLOUD_ROUTER_MONGO_URI` unset at deploy
time keeps `cloud_router/` running as the plain stateless proxy it always
was, with no embedded database mounted.

**Still to be designed/built** (tracked in `backlog.md`):
- A web GUI for editing the central catalog (no such GUI exists yet anywhere
  — today master data is only edited through the desktop app's admin panels
  over LAN/localhost).
- Durable `master_link` records tying an incident-local copy of a master
  record (e.g. a person added to an incident roster) back to the master
  record it came from, with two-way sync and surfaced conflicts.
- The actual sync mechanism between each server's local `sarapp_master` and
  this central database. A literal cross-WAN MongoDB replica set does not
  fit the existing dial-out tunnel topology (LAN servers are not
  independently reachable); the working plan is MongoDB change streams
  relayed over the existing tunnel/API channel instead — see the addition to
  `realtime_architecture_roadmap.md`.

