# web_client AGENTS

This directory is React/TypeScript (Vite), not Python — it's the one place
in the repo with Node/JS tooling. The root `agents.md` still applies for
anything cross-cutting (never hardcode the Mongo URI, never bypass the
`BaseRepository` write path, "incident" not "mission", etc.) but its
Python-specific rules (PEP 8, `styles/profiles/*.py` color tokens, PySide6
patterns) don't apply here.

## Scope
MVP only: login/check-in, role-based status updates (field) or admin
check-in (command), messaging. Mirrors the mobile MVP plan in
`Design Documents/Mobile/Phase 1 Design Document.txt`, not full desktop
parity. See `README.md` in this directory for dev/build instructions.

## Conventions
- `npm run build` outputs to `dist/`, which `create_app()`
  (`data/db/sarapp_db/api/app.py`) mounts at `/app` when present. Keep
  `vite.config.ts`'s `base: "/app/"` in sync with that mount path if it
  ever changes.
- Routing uses `HashRouter` (not `BrowserRouter`) specifically so the SPA
  works as plain static files with no server-side catch-all route — don't
  switch routers without adding that catch-all first.
- `src/api/client.ts` is the only place that should touch `fetch`/JWT
  storage; add new backend calls to `src/api/endpoints.ts` instead of
  calling `fetch` directly from a screen.
- The JWT this client gets from `/api/auth/login` is not yet enforced by
  any shared router (checkin/operations/chat/incidents) — see
  `Design Documents/Instructions/database_architecture.md`
  ("Authentication"). Don't assume server-side access control exists just
  because the client has a token.
