# SARApp Cloud Server DB

This folder hosts a VPS/container version of the SARApp server. It replaces
neither the old router container nor the user-facing connect flow. The hosted
server dials out to the old router and registers a connect code exactly like a
LAN server. To clients, it still looks like the existing cloud connect-code
flow:

```text
https://your-domain.example/r/<CONNECT_CODE>/health
https://your-domain.example/r/<CONNECT_CODE>/api/...
https://your-domain.example/r/<CONNECT_CODE>/dashboard
```

In the normal deployment, the old router owns `PathPrefix(/r/<CONNECT_CODE>)`
and forwards traffic down the registered tunnel. Direct Traefik routing to this
container is disabled by default and should only be enabled for diagnostics or
a deliberately separate direct-access deployment.

## First Install

Clone only the pieces this service needs with Git sparse checkout:

```bash
cd /opt
git clone --filter=blob:none --sparse https://github.com/RangerConlin/Incident-Management-Assistant.git sarapp-cloud-server-db
cd /opt/sarapp-cloud-server-db
git sparse-checkout set .dockerignore cloud_server data/db/sarapp_db
cd cloud_server
cp .env.example .env
nano .env
docker compose -p sarapp-cloud-server-db-test --env-file .env up -d --build
```

That checkout contains only:

- `.dockerignore`
- `cloud_server/`
- `data/db/sarapp_db/`

The required router registration settings in `cloud_server/.env` are:

- `SARAPP_CLOUD_ROUTER_URL`, for example `ws://sarapp-cloud:8765/tunnel/register`
- `SARAPP_CLOUD_ROUTER_TOKEN`, the same shared token LAN servers use
- `SARAPP_CONNECT_CODE`, the fixed code this server registers

## Updates

From the VPS:

```bash
cd /opt/sarapp-cloud-server-db/cloud_server
git -C .. pull --ff-only
docker compose -p sarapp-cloud-server-db-test --env-file .env up -d --build --remove-orphans
```

Or use the helper script:

```bash
cd /opt/sarapp-cloud-server-db/cloud_server
sh ./update_service.sh sarapp-cloud-server-db-test
```

The update keeps `cloud_server/.env` and Docker volumes in place.

## Multiple Servers On One VPS

Run one Compose project per server, each with:

- a unique `COMPOSE_PROJECT_NAME`
- a unique `SARAPP_CONNECT_CODE`
- its own MongoDB volume
- the same old router registration URL/token

Create another server by copying `.env.example` to a second env file with a
different project name and connect code:

```bash
docker compose -p sarapp-cloud-server-db-fair --env-file fair.env up -d --build
docker compose -p sarapp-cloud-server-db-storm --env-file storm.env up -d --build
```

## Dashboard

Open the dashboard through the same old-router connect-code URL:
`/r/<CONNECT_CODE>/dashboard`. Dashboard accounts are local to this server and
configured with:

- `CLOUD_ADMIN_USERNAME`
- `CLOUD_ADMIN_PASSWORD` or `CLOUD_ADMIN_PASSWORD_SHA256`
- `CLOUD_SESSION_SECRET`

The dashboard shows server status, MongoDB health, active client connections,
recent API traffic, backup export, backup import, and one-click updates.

## One-Click Updates

The update button is enabled by `CLOUD_UPDATE_COMMAND`. The browser never
supplies command text; the dashboard only starts the fixed command from the
environment and shows its recent output.

The default Compose file mounts the Docker socket and the sparse checkout into
the app container so this command can update the host deployment:

```env
CLOUD_UPDATE_COMMAND=cd /deploy/sarapp-cloud-server-db && git pull --ff-only && cd cloud_server && docker compose -p ${COMPOSE_PROJECT_NAME} --env-file .env up -d --build --remove-orphans
```

That is operationally convenient but powerful: anyone with dashboard admin
access can trigger a Docker rebuild/restart for this stack.

## Backup Import/Export

Exports are SARApp Mongo backup ZIP files with:

- `metadata.json`
- JSON dumps of `sarapp_system`, `sarapp_master`, and every
  `sarapp_incident_*` database

Imports never overwrite live databases. They restore into new database names
with the supplied suffix.

## Traefik

Direct Traefik exposure is off by default with `TRAEFIK_DIRECT_ENABLE=false`.
That avoids competing with the existing old router route. If you intentionally
turn it on, this Compose file assumes an existing external Docker network named
`traefik` and a Traefik HTTPS entrypoint named `websecure`. Override the
network name with `TRAEFIK_NETWORK`.

