# web_client AGENTS

This directory is React/TypeScript (Vite), not Python — it's the one place
in the repo with Node/JS tooling. The root `agents.md` still applies for
anything cross-cutting (never hardcode the Mongo URI, never bypass the
`BaseRepository` write path, "incident" not "mission", etc.) but its
Python-specific rules (PEP 8, `styles/profiles/*.py` color tokens, PySide6
patterns) don't apply here.

## Scope

Full-CRUD browser clone of the desktop app, built one module at a time —
not an MVP subset. No docking/floating-window UI parity; a browser-native
shell (sidebar + pages) instead. See `README.md` for dev/build instructions
and `src/shell/moduleRegistry.ts` for the full module list and which are
live vs. planned.

**Adding a new module**: add one entry to `moduleRegistry.ts` (flip
`status` to `"live"`, point `path` at the route), add the route in
`App.tsx`, and build the module under `src/modules/<area>/<name>/` following
the pattern in `src/modules/operations/teamStatus/` and `.../taskStatus/` —
a board page (`DataTable` + `StatusPill` + query hooks) and a detail page
(route-based, not a modal). Reuse the shared pieces below rather than
forking them per module.

## Conventions

- **Build/serve**: `npm run build` outputs to `dist/`, which `create_app()`
  (`data/db/sarapp_db/api/app.py`) mounts at `/app` when present. Keep
  `vite.config.ts`'s `base: "/app/"` in sync with that mount path if it
  ever changes.
- **Routing**: `HashRouter`, not `BrowserRouter` — the static mount in
  `app.py` has no server-side SPA catch-all, so a path like
  `/app/ops/teams/5` loaded directly would 404 under `BrowserRouter`. Don't
  switch without adding that catch-all first. Detail views are real routes
  (`/ops/teams/:teamId`), not modals — deep-linkable, support ctrl/
  middle-click "open in new tab," and back/forward returns to the board.
  Keep board filter/sort state in the URL query string, not component state
  only.
- **API calls**: `src/api/client.ts` is the only place that should touch
  `fetch`/JWT storage; add new backend calls to `src/api/endpoints.ts`
  instead of calling `fetch` directly from a module.
- **Connection target**: `src/api/connection.ts` owns where requests
  actually go — same-origin/relative by default ("internal"), or a stored
  domain + `cloud_router` connect code (`/connection` screen) when the app
  isn't already being served by the server it needs to talk to.
  `client.ts`'s `buildUrl` and `IncidentSocketProvider`'s `buildWsUrl` both
  go through it already; any new raw `fetch`/`WebSocket` call (there
  shouldn't be one — use `client.ts`) would need to as well. Does **not**
  fix the SPA's own bundle loading through a connect-code URL — see
  README.md's "Connection settings" section for that gap.
- **Data fetching**: TanStack Query (`@tanstack/react-query`), one
  `QueryClientProvider` in `main.tsx`. Each module's `hooks.ts` wraps
  `endpoints.ts` functions as `queryFn`/`mutationFn`. Query key convention:
  `["incident", incidentId, <mongo-collection-name>, ...]` — e.g.
  `["incident", id, "teams"]` for the board, `["incident", id, "teams",
  teamId]` for a detail record. This convention is load-bearing: see
  real-time below.
- **Real-time**: `src/realtime/IncidentSocketProvider.tsx` opens the
  incident's WebSocket once (`/api/incidents/{id}/ws`, already broadcasting
  on every `BaseRepository` write — see `data/db/sarapp_db/api/ws_hub.py`)
  and treats every message as a pure invalidation signal:
  `queryClient.invalidateQueries(["incident", incidentId, msg.collection])`.
  TanStack Query's partial key matching invalidates both the board's list
  query and any open detail query for that collection in one call — this is
  *why* the query key convention above matters. Don't reconstruct a
  client-side join from the raw pushed document; let the row endpoint
  refetch and rejoin server-side. Every query that backs a board or detail
  view should also set a `refetchInterval` (~20s) as a permanent polling
  floor — not a stopgap, the reconnect-gap safety net.
- **Shared table UI** (`src/components/table/`): `DataTable` (sortable/
  resizable columns, persisted per-table via `useColumnPrefs`,
  double-click → `onRowActivate`), `StatusPill`, `FilterBar`,
  `RowContextMenu`, `ElapsedTime`. Use these for every new board/list view
  instead of a bespoke table — only the column defs, filter fields, and
  menu items are module-specific.
- **Selected-row outline**: `DataTable` renders selection as an outline,
  never a fill (agents.md's hard rule for every table in this app, Python
  or web). Don't add alternating row colors or a selected-row background.
- **Status colors**: `src/styles/statusColors.css` + `.ts` are the web
  analog of `styles/profiles/{dark,light}.py` — same keys, same hex values,
  hand-maintained side by side with those two files (no shared source,
  same as the Python pair). A new status vocabulary (e.g. for the Intel
  module) is one more CSS var block-pair + one more key union in
  `statusColors.ts`, nothing else changes. Theme is a `data-theme` attribute
  on `<html>` (`applyTheme`/`getStoredTheme`), not a React re-render.
- **Auth**: the JWT from `/api/auth/login` is enforced by **no router at
  all** today — this was attempted in a tunnel-scoped form and reverted
  (see `backlog.md`'s `web_client` entry). Don't assume server-side access
  control exists just because the client has a token.
