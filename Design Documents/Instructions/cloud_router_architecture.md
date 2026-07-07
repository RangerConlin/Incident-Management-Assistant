# Cloud Router (Reverse Tunnel) Architecture

## Purpose
`cloud_server/` is a stateless reverse-proxy router, not a second SARApp
backend. Field/remote devices are not on the incident command post's (ICP)
LAN, so they can't reach the LAN server directly. The LAN server dials
**out** to the cloud router on startup (a reverse tunnel — ICP networks are
typically behind NAT with no inbound port-forwarding), registers itself under
a connect code, and the router forwards field-device HTTP and WebSocket
traffic down that tunnel. All data access, business logic, and auth stay on
the LAN server; the router never touches MongoDB and never runs any
`sarapp_db` router.

## Roles
- **LAN server** (`lan_server/`): runs the real `sarapp_db` FastAPI app
  (`data/db/sarapp_db/api/app.py`) on its own uvicorn instance, same as
  always. Additionally owns `lan_server/cloud_tunnel_client.py`, which — if
  configured — opens one persistent outbound WebSocket to the cloud router
  and answers forwarded requests by calling the local app over loopback.
- **Cloud router** (`cloud_server/router/`): a small FastAPI app
  (`cloud_server/router/app.py`) with no Mongo dependency. Accepts LAN
  server tunnel registrations and proxies field-device HTTP/WebSocket
  traffic to the matching tunnel. `cloud_server/router/registry.py` holds
  the in-memory table of currently-connected LAN servers.
- **Field device**: any SARApp client not on the ICP LAN. The desktop client
  resolves its cloud fallback URL at startup (`_resolve_cloud_url` in
  `main.py`) with this priority: `SARAPP_CLOUD_URL` env var (full URL, may
  already include `/r/<code>`) > Settings → Connection (`cloudServerUrl` +
  `cloudConnectCode`, combined via
  `core.networking.build_cloud_url` into `<url>/r/<code>`) > built-in default
  URL. The existing LAN→cloud fallback flow
  (`ConnectionManager.try_cloud_connection`) then health-checks that URL —
  the router's `/r/<code>/health` proxies straight through to the LAN
  server's real `/health` — and `ServerInfo.base_url` keeps the full tunnel
  path so all subsequent API traffic goes through the router.

## Connect codes
- A short, human-shareable code (e.g. `ABCD-1234`) identifies one LAN
  server's tunnel. There is no public directory of active codes — the IC
  hands the code to field teams out-of-band (radio, briefing, etc.).
- Configured via `SARAPP_CONNECT_CODE`; if unset, the LAN server
  auto-generates one and logs it prominently at startup so an operator can
  read it off the console.
- Many LAN servers (ICPs) can be registered with one cloud router
  simultaneously, each under its own code (`TunnelRegistry` is a table, not a
  single slot).

## Auth model (two independent layers)
1. **Tunnel registration** (LAN server → cloud router): a shared secret,
   `SARAPP_CLOUD_ROUTER_TOKEN`, must match on both sides or the router closes
   the connection. This only proves the LAN server is legitimate — it has
   nothing to do with individual field-device users.
2. **Field device → LAN server**: pass-through only. The router does not
   authenticate or inspect field-device credentials; whatever auth the LAN
   server's own `auth_sessions` router enforces today still applies
   identically once a proxied request reaches it.

Never hardcode `SARAPP_CLOUD_ROUTER_TOKEN`; read it from the environment only
(same rule as `SARAPP_MONGO_URI`).

## Tunnel protocol
One physical WebSocket connection per LAN server (`/tunnel/register` on the
router) carries every frame for that LAN server, distinguished by a `type`
field. Two independent frame families are multiplexed over it:

### Registration
```json
// LAN server -> router, once, first message
{"type": "register", "connect_code": "ABCD-1234", "server_id": "...", "server_name": "...", "token": "..."}
// router -> LAN server, on success
{"type": "registered"}
```
On mismatch/invalid registration the router closes the WebSocket instead of
replying.

### HTTP request/response (many concurrent, keyed by `request_id`)
```json
// router -> LAN server
{"type": "request", "request_id": "...", "method": "GET", "path": "/api/...", "query": "a=1", "headers": {...}, "body": "<base64>"}
// LAN server -> router
{"type": "response", "request_id": "...", "status": 200, "headers": {...}, "body": "<base64>"}
```
A field-device HTTP call to `https://cloud/r/<code>/api/...` becomes one
`request`/`response` pair. The router times out and returns `504` if no
matching `response` arrives (default 30s); it returns `503` if `<code>` isn't
currently registered.

### WebSocket multiplexing (many concurrent, keyed by `channel_id`)
```json
// router -> LAN server, when a field device opens a WS through the router
{"type": "ws_open", "channel_id": "...", "path": "/api/incidents/{id}/ws"}
// either direction, per message
{"type": "ws_message", "channel_id": "...", "data": "...", "binary": false}
// either direction, on close
{"type": "ws_close", "channel_id": "..."}
```
A field device opening `wss://cloud/r/<code>/api/incidents/{id}/ws` gets a
`channel_id` minted by the router; the LAN-side tunnel client opens its own
local WebSocket to that same path on `127.0.0.1` and relays messages both
ways. This is what lets field devices get the same live-update push
(`ws_hub.py` broadcasts) as LAN clients, not just request/response.

## Known v1 limitations
- Large binary bodies (photo/file uploads) travel as base64-in-JSON, not
  streamed. Fine for typical form/photo sizes; revisit if uploads get large
  enough to matter.
- No public "list active servers" endpoint — matches the deliberate
  manual-code-entry model.

## Env vars
| Variable | Set on | Purpose |
| --- | --- | --- |
| `SARAPP_CLOUD_ROUTER_URL` | LAN server | WebSocket URL of the cloud router's `/tunnel/register`. Unset = tunneling disabled, zero behavior change. |
| `SARAPP_CLOUD_ROUTER_TOKEN` | both | Shared secret for tunnel registration. |
| `SARAPP_CONNECT_CODE` | LAN server | Optional; auto-generated and logged if unset. |

When the LAN server is launched through the SARApp Server Console
(`lan_server/server_console/`), the cloud router URL and connect code can also
be set in the console's Settings panel (persisted in `server_console.json`);
those values take precedence over the environment variables. The registration
token remains env-only (`SARAPP_CLOUD_ROUTER_TOKEN`) and is never persisted.
