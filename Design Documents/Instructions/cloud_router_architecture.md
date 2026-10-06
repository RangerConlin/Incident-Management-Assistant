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

