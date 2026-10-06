# SARApp Cloud Server DB Update Flow

This service is deployed on the VPS from a sparse Git checkout. The VPS does
not need the full desktop repo.

## Update Existing Service

Run this on the VPS:

```bash
cd /opt/sarapp-cloud-server-db
git pull --ff-only
cd cloud_server
docker compose -p sarapp-cloud-server-db-test --env-file .env up -d --build --remove-orphans
```

From Windows, double-click `cloud_server/update_vps_cloud_server_db.cmd` or
make a desktop shortcut to it. The shortcut opens SSH to the VPS, runs the same
update flow, shows `docker compose ps`, and leaves the SSH session open in
`/opt/sarapp-cloud-server-db/cloud_server`.

Check the app logs:

```bash
docker compose -p sarapp-cloud-server-db-test --env-file .env logs -f app
```

The old router dashboard should continue showing the server as connected under
the configured `SARAPP_CONNECT_CODE`.

## First-Time Sparse Checkout

Run this only when setting up the VPS directory from scratch:

```bash
cd /opt
git clone --filter=blob:none --sparse https://github.com/RangerConlin/Incident-Management-Assistant.git sarapp-cloud-server-db
cd /opt/sarapp-cloud-server-db
git sparse-checkout set --no-cone /.dockerignore /cloud_server/ /data/db/sarapp_db/
cd cloud_server
cp .env.example .env
nano .env
docker compose -p sarapp-cloud-server-db-test --env-file .env up -d --build
```

Minimum required `.env` settings:

```env
COMPOSE_PROJECT_NAME=sarapp-cloud-server-db-test
SARAPP_CONNECT_CODE=DEMO-0001
SARAPP_CLOUD_ROUTER_URL=ws://sarapp-cloud:8765/tunnel/register
SARAPP_CLOUD_ROUTER_TOKEN=<old-router-token>
TRAEFIK_DIRECT_ENABLE=false
TRAEFIK_NETWORK=cloud_server_sarapp-net
CLOUD_ADMIN_USERNAME=admin
CLOUD_ADMIN_PASSWORD=<dashboard-password>
CLOUD_SESSION_SECRET=<long-random-string>
CLOUD_UPDATE_COMMAND=cd /deploy/sarapp-cloud-server-db && git pull --ff-only && cd cloud_server && docker compose -p ${COMPOSE_PROJECT_NAME} --env-file .env up -d --build --remove-orphans
```

Generate `CLOUD_SESSION_SECRET` with:

```bash
openssl rand -base64 48
```
