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

## Auth scope

Login is password/JWT-based (`POST /api/auth/password/set`,
`POST /api/auth/login`), currently only used by this web client. **No
router enforces that token today** — this was tried and deliberately
reverted (see `backlog.md`'s `web_client` entry and
`Design Documents/Instructions/database_architecture.md`'s "Authentication"
section for why: the LAN tunnel is currently broken, so enforcing auth on
tunnel-arrived traffic would effectively require it on all real desktop/
mobile traffic today, with no way for those clients to send a token).
