# SARApp Cloud Router

This is the stateless reverse-tunnel proxy that owns the public
`https://<domain>/r/<CONNECT_CODE>/...` URL shape. LAN servers and the
hosted `cloud_server/` backend each dial **out** to this service over a
websocket and register a connect code; field/remote clients hit
`/r/<connect_code>/...` here and their requests are forwarded down the
matching tunnel. It never imports `sarapp_db` and never talks to MongoDB
directly — it has no idea what's inside the requests it forwards.

**This code was deleted from the repo on 2026-10-06** (commit `fed5fbcc`)
when `cloud_server/` was rewritten from "stateless router" into today's
LAN-equivalent hosted backend. The router itself was never decommissioned,
though — per `cloud_server/README.md`, the new `cloud_server/` backend
*also* dials out and registers with this same router, exactly like a LAN
server does. It is still live production infrastructure (deployed as the
`sarapp-cloud` container, port 8765), so its source was restored here from
git history (`fed5fbcc^:cloud_server/`) rather than being left only
reachable via `git show`.

`cloud_router/` and `cloud_server/` are two independent services that do
not share any files or imports:

- `cloud_router/` (this directory) — the always-on public proxy. Stateless,
  no database, no incident data.
- `cloud_server/` — a hosted LAN-server-equivalent backend. Owns incident
  data (its own MongoDB), serves the real SARApp API, and is one of
  potentially several backends this router can tunnel traffic to.

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
