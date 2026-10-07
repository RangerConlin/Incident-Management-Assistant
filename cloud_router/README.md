# SARApp Cloud Router

This is the reverse-tunnel proxy that owns the public
`https://<domain>/r/<CONNECT_CODE>/...` URL shape. LAN servers and the
hosted `cloud_server/` backend each dial **out** to this service over a
websocket and register a connect code; field/remote clients hit
`/r/<connect_code>/...` here and their requests are forwarded down the
matching tunnel. It still has no idea what's inside the requests it
forwards, and never holds or forwards *incident* data of its own.

`cloud_router/` and `cloud_server/` are two independent services that do
not share any files or imports:

- `cloud_router/` (this directory) — the always-on public proxy, plus (see
  below) the embedded agency-wide master-catalog database. No incident data.
- `cloud_server/` — a hosted LAN-server-equivalent backend. Owns incident
  data (its own MongoDB), serves the real SARApp API, and is one of
  potentially several backends this router can tunnel traffic to.

## Central master database (2026-10)

cloud_router now optionally owns its own embedded MongoDB instance, holding
the authoritative, centralized agency-wide catalog (`sarapp_central_master`
— personnel, equipment, vehicles, aircraft, hospitals, certifications,
organizations, templates, forms, etc.). This deliberately changes the "no
database" rule described above and in `agents.md`'s hard rules — it was a
confirmed, intentional decision, not drift, made because every LAN/cloud
server previously ran its own disconnected copy of this catalog with no
central source of truth.

This does **not** reintroduce incident data into cloud_router, and does not
merge `cloud_router/` and `cloud_server/` back together: `cloud_server/` and
LAN servers remain the only owners of incident/system data. The central
database reuses the existing master-catalog routers/schemas from
`data/db/sarapp_db/` unmodified (via `sarapp_db.api.app.create_app(mode=
"master_only")`, mounted at `/central-master` by `master_db/app.py`) rather
than duplicating any router or schema code, and it's optional: leaving
`SARAPP_CLOUD_ROUTER_MONGO_URI` unset keeps cloud_router running as the
plain stateless proxy it always was. See
`Design Documents/Instructions/cloud_router_architecture.md` for the full
design, including the still-open design work: a web GUI for editing this
catalog, durable incident↔master record links, and change-stream-based
sync between this central database and each server's local `sarapp_master`.

## Running

```bash
cd cloud_router
cp .env.example .env   # if/when one exists; see docker-compose.yml for the
                        # required environment variables in the meantime
docker compose up -d --build
```

Required environment variables (see `docker-compose.yml`):

- `SARAPP_CLOUD_ROUTER_TOKEN` — shared secret LAN/cloud servers must present
  to register a tunnel.
- `SARAPP_SERVER_NAME` (optional)
- `SARAPP_ROUTER_*` tuning knobs (request timeout, heartbeat interval,
  max pending requests, max body bytes, register rate limit) — see
  `router/config.py`.

## Deploying the VPS checkout

The server this code is already running on was checked out before this
restoration — point its checkout at a commit that includes `cloud_router/`
(any commit after this restoration) and rebuild from `cloud_router/` instead
of the old `cloud_server/` path it used previously.
