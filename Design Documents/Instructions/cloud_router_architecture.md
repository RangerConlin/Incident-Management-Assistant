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

**Web GUI (MVP, `cloud_router/master_db/webgui.py`):** a plain server-rendered
HTML + vanilla-JS-free CRUD GUI at `/central-master/gui/...` (same
session-cookie admin login pattern as `cloud_server/dashboard.py`, env vars
`CENTRAL_MASTER_ADMIN_USERNAME`/`CENTRAL_MASTER_ADMIN_PASSWORD[_SHA256]`/
`CENTRAL_MASTER_SESSION_SECRET`). Covers `personnel` and `equipment` so far
— each collection's editable fields are declared explicitly in a
`CollectionSpec` (most master routers take loose `dict[str, Any]` bodies
rather than a strict Pydantic request model, so there is no schema to
introspect generically). The GUI never touches Mongo directly: each
`CollectionSpec` wraps the *same* master-router functions the
`/central-master/api/master/...` HTTP routes call (e.g.
`sarapp_db.api.routers.personnel.create_person`), invoked in-process as
plain Python functions rather than looping an HTTP call back into the same
app — the code path is identical either way. Extending to more collections
is tracked in `backlog.md`.

**Server ↔ central sync relay (`data/db/sarapp_db/sync/`):** implemented as
push-on-write with a local outbox, not MongoDB change streams — every
deployment today runs a standalone `mongod` (no replica set, which change
streams require even for a single node), so this was built to work with
what's actually deployed rather than requiring an infrastructure migration
first. See the "Server ↔ central sync" section in
`realtime_architecture_roadmap.md` for the full design and why. In brief:
`BaseRepository.insert_one`/`update_one`/`apply_update` call
`sync.relay.relay_local_write()` for any write to a collection in
`sync.config.SYNCABLE_MASTER_COLLECTIONS` (currently just `personnel`) on a
server's *local* `sarapp_master` (never on `sarapp_central_master` itself,
so cloud_router's own writes don't loop back into "relay to central") —
this attempts an immediate HTTP push to `/api/sync/push` on the central
database (`data/db/sarapp_db/api/routers/sync.py`, mounted only in
`mode="master_only"`), and queues it in a local outbox
(`sarapp_system.sync_state`) for retry if that fails (e.g. offline).
`sync.loop.CentralSyncLoop` (a daemon thread started by `lan_server/
server_manager.py` and `cloud_server/main.py`, no-oping when
`SARAPP_CENTRAL_MASTER_URL` is unset) periodically drains that outbox and
pulls down anything changed centrally since each collection's last
checkpoint (`sarapp_system.sync_pull_checkpoints`). Conflicts resolve by
pure last-write-wins on `updated_at` — no logging, no review step; two
genuinely simultaneous edits aren't a realistic case worth building a
review workflow around, so whichever write has the newer timestamp simply
wins (ties go to the incoming write). `data/db/sync_local_to_cloud.py` (the
old one-way full-replace script) no longer touches `sarapp_master` at all,
to avoid clobbering this relay's state; it's scoped to incident database
mirroring only now.

Deletes relay too: `BaseRepository.delete_one` (hard delete, used by
`soft_deletes=False` collections like `equipment`) relays via a
`MasterCollections.SYNC_TOMBSTONES` marker, kept separately from the real
collection so a literal removal centrally doesn't go undiscovered by a
later pull. A `soft_deletes=True` collection's own soft-deletes already
relay for free through the ordinary upsert path — see the "Deletes" bullet
in `mongodb_schema_decisions.md`'s "Central-Master Sync Relay" section for
the full mechanics.

Master vs. incident data, by design: the master catalog is pre-filled
reference data that exists to make retrieving a full record fast (type a
name, get back rank/callsign/phone/etc. instead of typing it all by hand).
An incident's copy is a one-time download of that reference data into the
incident — once copied, it's independent, and is never automatically
re-synced just because the master record changed later. (An earlier version
of this work added exactly that kind of continuous reconciliation; it was
deliberately removed as inconsistent with this model — see
`mongodb_schema_decisions.md` "Master-Incident Record Linking.")

**Still to be designed/built** (tracked in `backlog.md`):
- Generalizing the web GUI from 2 collections to the full ~40-collection
  inventory, and per-operator accounts/an audit trail (MVP is one shared
  admin login).
- Extending the sync relay beyond `personnel`/`equipment` to the other
  syncable master collections.

