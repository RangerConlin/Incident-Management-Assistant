# SARApp Web Client

MVP web client scoped to the same feature set as the mobile app plan
(`Design Documents/Mobile/Phase 1 Design Document.txt`): login, incident
selection, check-in, role-based status updates / admin check-in, and
messaging. It talks to the same shared FastAPI app every other client uses
(`data/db/sarapp_db/api/app.py`) — no separate backend.

## Dev

```
npm install
npm run dev
```

The dev server proxies `/api`, `/health`, and `/server-info` to a backend
running at `http://localhost:8000` by default. Point it elsewhere with:

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
`POST /api/auth/login`), currently only used by this web client. The shared
routers it calls (checkin, operations, chat, incidents) do not yet require
that token — see `Design Documents/Instructions/database_architecture.md`.
