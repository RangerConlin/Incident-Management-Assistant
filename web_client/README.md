# SARApp Web Client

A browser-based, full-CRUD clone of the desktop app, built module by module.
Aimed at command-post users who want incident access without installing the
PySide6 desktop client — "reach," not a field-ops companion. No docking/
floating-window UI parity with desktop: a browser-native shell (sidebar nav +
pages) instead. It talks to the same shared FastAPI app every other client
uses (`data/db/sarapp_db/api/app.py`) — no separate backend.

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

## Connection settings

By default every request is same-origin/relative ("internal" — whatever
server is already serving this page: a LAN server, an offline server, or a
cloud server reached directly). `/connection` (linked from the login screen
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
reverted (see `backlog.md`'s `web_client` entry and
`Design Documents/Instructions/database_architecture.md`'s "Authentication"
section for why: the LAN tunnel is currently broken, so enforcing auth on
tunnel-arrived traffic would effectively require it on all real desktop/
mobile traffic today, with no way for those clients to send a token).
