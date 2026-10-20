# SARApp Web Client

A browser-based, full-CRUD clone of the desktop app, built module by module.
Aimed at command-post users who want incident access without installing the
PySide6 desktop client — "reach," not a field-ops companion. No docking/
floating-window UI parity with desktop: a browser-native shell (sidebar nav +
pages) instead. It talks to the same shared FastAPI app every other client
uses (`server/sarapp_db/sarapp_db/api/app.py`) — no separate backend.

First module built (the template every later module copies): the **Team
Status Board** and **Task Status Board**, plus their detail pages
(`src/modules/operations/{teamStatus,taskStatus}/`). See `src/shell/
moduleRegistry.ts` for the full planned module list and which are live.

An earlier MVP mirroring the mobile app's field-user plan (login → check-in
→ status updates / admin check-in / messaging) was scrapped in favor of this
direction — its screens are gone, but the auth/API-client plumbing carried
over.

## Dev

```
npm install
npm run dev
```

The dev server proxies `/api` (including the incident WebSocket), `/health`,
and `/server-info` to a backend running at `http://localhost:8000` by
default. Point it elsewhere with:

```
VITE_BACKEND_PROXY_TARGET=http://localhost:9000 npm run dev
```

## Build

```
npm run build
```

Outputs to `dist/`. When that directory exists, `create_app()` mounts it at
`/app` so the LAN server, cloud server, and built-in offline server all
serve it automatically — no separate deploy step.

## Deployment

Two independent ways to serve the built app — pick one per deployment, not
both:

1. **Embedded**: `create_app()` (`server/sarapp_db/sarapp_db/api/app.py`) mounts
   `dist/` at `/app` automatically when it exists, so the LAN server, cloud
   server, and built-in offline server serve it for free, same-origin with
   their own API. No container of its own.
2. **Standalone container** (this directory's `Dockerfile` +
   `docker-compose.yml`): a self-contained image — Node build stage, then
   nginx serving the result — with its own Traefik labels, same packaging
   style as `cloud_server/` and `cloud_router/` but with no shared files or
   images with either. No database of its own, but it does need to know
   which backend to reach: nginx reverse-proxies `/api/` (REST and the
   incident WebSocket, which lives under `/api/incidents/{id}/ws`) to that
   backend's public connect-code URL — the same way desktop/mobile already
   reach it, through `cloud_router` — so the container works for anyone who
   opens this domain, no per-browser setup required. The `/connection`
   screen below still exists client-side as an override for pointing one
   browser at a *different* server than the one this deployment was built
   for.

   ```
   cd apps/web
   docker compose up -d --build
   ```

   Configurable via env vars (`.env` in this directory, gitignored —
   deployment-specific values never get committed, same convention as
   `cloud_server`'s `SARAPP_CONNECT_CODE`; Compose reads this file
   automatically, no `--env-file` flag needed):
   - `SARAPP_BACKEND_HOST` (required) — the `cloud_router` host this
     deployment's data lives behind (e.g. the domain desktop/mobile already
     use for this incident's server).
   - `SARAPP_BACKEND_CONNECT_CODE` (required) — the connect code that
     backend registers under.
   - `COMPOSE_PROJECT_NAME`, `SARAPP_WEB_CLIENT_ROUTE_RULE` (Traefik router
     rule — defaults to serving under `/app` on whatever domain Traefik
     already fronts; set to a `Host(...)` rule for a dedicated subdomain
     instead).

   Production target: `client.arcadiacommandsolutions.com`, as its own
   subdomain, backed by the `cloud_server` already running on the same
   VPS. The actual host/connect-code values are deployment-specific and
   live only in that VPS's own `apps/web/.env` (gitignored) — not
   documented here.

   Needs DNS for that subdomain pointed at the VPS (outside this repo).
   TLS is expected to come from whatever default cert resolver Traefik on
   this VPS already applies — neither `cloud_server/docker-compose.yml`
   nor `cloud_router/docker-compose.yml` sets a per-router `certresolver`
   label either, so Traefik's static config evidently has a default one.
   Not independently confirmed for a brand-new host/domain; if a cert
   doesn't issue automatically, check that static config before adding a
   `certresolver` label here.

   No shared Traefik network to configure — this container doesn't join
   one. Confirmed on the actual VPS (`docker network ls`): Traefik there
   runs with `--network host` and reaches containers via the Docker
   socket + their own bridge IP, the same way `cloud_server`/`cloud_router`
   each sit on their own private per-project network rather than a shared
   external one. Only the Traefik labels matter for discovery.

   Reached this way, the app's own bundle loads directly under `/app` with
   no connect-code prefix involved — the "known limitation" below is about
   the *embedded* path reached through `cloud_router`'s tunnel, not this
   container.

## Connection settings

By default every request is same-origin/relative ("internal" — whatever
server is already serving this page: a LAN server, an offline server, a
cloud server reached directly, or — for the standalone container — nginx
itself forwarding to the backend configured via `SARAPP_BACKEND_HOST`/
`SARAPP_BACKEND_CONNECT_CODE` above). `/connection` (linked from the login screen
and the app's top bar) lets a user instead point the app at a domain +
`cloud_router` connect code (`src/api/connection.ts`), for when this app is
opened from somewhere that isn't already the right server. Every API call
and the incident WebSocket go through `buildUrl`/`buildWsUrl` there, which
prepend `https://<domain>/r/<code>` when a domain is set and fall back to
same-origin otherwise.

**Known limitation**: this only affects data calls made *after* the app has
loaded — it does not help the app's own bundle load correctly through a
`/r/<code>/app/...` URL in the first place. `vite.config.ts`'s
`base: "/app/"` bakes absolute asset paths into `index.html`
(`/app/assets/...`); a browser resolves those against the current origin
with no path prefix, so if `index.html` itself was fetched through
`cloud_router`'s connect-code prefix, the follow-up asset requests lose
that prefix and 404 (`cloud_router/router/app.py`'s proxy strips the
prefix before forwarding, but only for the request it already received —
it does not rewrite HTML it returns). Not fixed yet; tracked in
`backlog.md`. Today this app needs to be reached without a connect-code
prefix on its *own* URL (serving it, not calling its API) for the initial
load to work.

## Auth scope

Login is password/JWT-based (`POST /api/auth/password/set`,
`POST /api/auth/login`), currently only used by this web client. **No
router enforces that token today** — this was tried and deliberately
reverted (see `backlog.md`'s `apps/web` entry and
`docs/archive/design-documents/Instructions/database_architecture.md`'s "Authentication"
section for why: the LAN tunnel is currently broken, so enforcing auth on
tunnel-arrived traffic would effectively require it on all real desktop/
mobile traffic today, with no way for those clients to send a token).

## Validation

Run `npm test` for the browser client's focused Node tests, and `npm run build`
for TypeScript checking and the production bundle. PAO tests cover draft/update
metadata handling, release lifecycle actions, URL-filter model behavior, timestamp
conversion, and safe rendering of release/template text. They do not replace a
live-server browser acceptance pass.

Public Information is available under `#/pio`. Publication records lifecycle
status; external delivery is performed separately and recorded in the distribution
log. Server write-layer and concurrent-edit gaps are tracked in `backlog.md`.

## Downloadable ICS forms

The Forms workspace and export controls on Objectives, Work Assignments, SITREPs,
Meetings, Check-In and Resource Requests download PDFs from the shared API. Supported
forms are ICS 202, 204, 209, 211, 213RR, 215, 215A and 230. ICS 209/215 use the existing
ICS Canada templates; other entries use the FEMA template set, as labeled in the picker.
ICS 230's source template includes its standard preprinted common-meeting guide.

Downloads contain saved source data, with repeated rows paginated and continuation text
preserved. The PDFs remain editable; signatures are not manufactured. Incident-wide
ICS 202 includes active objectives and ICS 230 includes meetings marked for its schedule;
board search filters are not export filters. Check-In exports currently checked-in resources.

The server needs its updated Python dependencies and bundled export assets. Cloud packaging
copies these inside the shared `sarapp_db` package; no desktop installation is required.
Verify asset copies with `python tools/scripts/sync_server_form_templates.py --check`.
Backend regression tests: `PYTHONPATH=server/sarapp_db python -m pytest
server/sarapp_db/sarapp_db/api/routers/tests/test_form_exports.py -q` (set `PYTHONPATH`
with your shell's environment syntax). They do not require a running MongoDB server.
