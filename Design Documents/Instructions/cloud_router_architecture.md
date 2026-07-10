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
  It replies to `ping` heartbeats, logs (rather than silently drops) any
  frame type it doesn't recognize, defensively re-checks the request body
  size cap, bounds its own concurrent in-flight frame handling with a
  semaphore sized to match the router's per-tunnel request cap, and inspects
  the WebSocket close code on disconnect to back off longer after an
  auth-rejection (`1008`) than after a routine drop.
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
- **Deliberately no expiry/rotation.** Connect codes are long-lived and
  manually shared by design, not a security boundary on their own — the real
  protection against an unauthorized LAN server registering is the shared
  `SARAPP_CLOUD_ROUTER_TOKEN` (below). This was reconsidered during the
  mobile-hardening pass and kept as-is intentionally; revisit only if code
  leakage/abuse becomes a real operational problem.

## Auth model (two independent layers)
1. **Tunnel registration** (LAN server → cloud router): a shared secret,
   `SARAPP_CLOUD_ROUTER_TOKEN`, must match on both sides (compared with
   `hmac.compare_digest` to avoid timing attacks) or the router closes the
   connection with code `1008`. This only proves the LAN server is
   legitimate — it has nothing to do with individual field-device users.
   `/tunnel/register` is also rate-limited per source IP
   (`SARAPP_ROUTER_REGISTER_RATE_LIMIT`, default 10/minute) to blunt brute-
   force/registration-flood attempts; this is an in-memory, single-process
   limiter, not a distributed one.
2. **Field device → LAN server**: pass-through only. The router does not
   authenticate or inspect field-device credentials; whatever auth the LAN
   server's own `auth_sessions` router enforces today still applies
   identically once a proxied request reaches it.
3. **Admin endpoints** (`/admin/tunnels`, `/admin/metrics`): gated by the
   same `SARAPP_CLOUD_ROUTER_TOKEN` shared secret, passed as an
   `X-Router-Token` header. No second auth mechanism.

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

### Heartbeat (keeps the tunnel's liveness honest)
```json
// router -> LAN server, every SARAPP_ROUTER_HEARTBEAT_INTERVAL_SECONDS (default 15s)
{"type": "ping", "ts": 1234567890.12}
// LAN server -> router, immediately on receipt
{"type": "pong", "ts": 1234567890.12}
```
If the router doesn't see a `pong` within
`SARAPP_ROUTER_HEARTBEAT_TIMEOUT_SECONDS` (default 45s) of the last one, it
treats the tunnel as dead: closes the registration socket (code `1001`),
deregisters the connect code, and immediately fails every pending
`request`/`ws` future instead of waiting on the per-request timeout. This is
additive — an un-upgraded LAN client that doesn't reply to `ping` is simply
treated as dead once the timeout elapses (safe degradation), but should be
upgraded promptly since it will otherwise get disconnected and have to
reconnect from scratch every heartbeat-timeout window.

### HTTP request/response (many concurrent, keyed by `request_id`)
```json
// router -> LAN server
{"type": "request", "request_id": "...", "method": "GET", "path": "/api/...", "query": "a=1", "headers": {...}, "body": "<base64>"}
// LAN server -> router
{"type": "response", "request_id": "...", "status": 200, "headers": {...}, "body": "<base64>"}
```
A field-device HTTP call to `https://cloud/r/<code>/api/...` becomes one
`request`/`response` pair. The router times out and returns `504` if no
matching `response` arrives (`SARAPP_ROUTER_REQUEST_TIMEOUT_SECONDS`, default
30s — the LAN server's own loopback timeout should be set to the same value
or lower, or the router may time out while the LAN server is still working).
It returns `503` if `<code>` isn't currently registered, `503` if the tunnel
is at its per-tunnel concurrency cap (`SARAPP_ROUTER_MAX_PENDING_REQUESTS`,
default 200 in-flight requests), and `413` if the request body exceeds
`SARAPP_ROUTER_MAX_BODY_BYTES` (default 20MB) — enforced on both the router
and, defensively, the LAN client.

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
(`ws_hub.py` broadcasts) as LAN clients, not just request/response. A tunnel
at its per-tunnel channel cap (`SARAPP_ROUTER_MAX_WS_CHANNELS`, default 100)
rejects new field-device WS connections with close code `1013`.

When the router closes a field device's WebSocket — because the underlying
tunnel dropped, or the LAN server sent a normal `ws_close` — it now sends a
distinguishing close code/reason so mobile clients can tell the two apart:
`1001`/`"tunnel_disconnected"` if the LAN server's tunnel itself went away,
`1000`/`"remote_closed"` for a normal LAN-server-initiated close. This
close-code distinction is router → field-device only; it is never sent over
the wire to the LAN server.

## Known v1 limitations
- Large binary bodies (photo/file uploads) travel as base64-in-JSON, not
  streamed, and are capped by `SARAPP_ROUTER_MAX_BODY_BYTES` (default 20MB) —
  fine for typical form/photo sizes but not appropriate for large file
  transfers. The real fix, deferred for now, is a v2 chunked frame family
  (`request_start` / `request_chunk` (with a `seq` field) / `request_end`)
  that the router streams via `Request.stream()` and the LAN client streams
  into an `httpx` streaming upload, keeping memory proportional to chunk
  size rather than full body size.
- No public "list active servers" endpoint for field devices — matches the
  deliberate manual-code-entry model. (There is now an *operator-only*
  `/admin/tunnels` endpoint, gated by the shared token — see below.)
- The registration rate limiter (`/tunnel/register`) is in-memory and
  per-process; it would need shared state (e.g. Redis) if the router is ever
  horizontally scaled to multiple instances.

## Operational endpoints
Both require the `X-Router-Token` header to match `SARAPP_CLOUD_ROUTER_TOKEN`.
- `GET /admin/tunnels` — per-tunnel connect code, server id/name, seconds
  since connected, seconds since last heartbeat pong, pending request count,
  open ws channel count.
- `GET /admin/metrics` — process-wide counters: total requests, timeouts,
  503s, 413s, ws channels opened, heartbeat timeouts, registration
  rejections, plus the current active tunnel count.

## Status dashboard (unauthenticated)
- `GET /dashboard` — a small self-contained HTML page (`cloud_server/router/dashboard.py`)
  that polls `GET /dashboard/data` every 3s and renders connected LAN
  servers plus the same counters as `/admin/metrics`.
- `GET /dashboard/data` — the JSON this page polls: `active_tunnel_count`,
  a `tunnels` list (same shape as `/admin/tunnels`), and a `metrics` object
  (same shape as `/admin/metrics`).
- **Deliberately not token-gated**, unlike `/admin/*` — a conscious choice
  for ease of glancing at router health, not an oversight. It only exposes
  connect codes, server names, and counts (all already low-sensitivity —
  connect codes are shared out-of-band by design, see above) and has no
  ability to act on a tunnel. If that tradeoff needs revisiting later, gate
  it the same way as `/admin/*`.

## Testing the mobile -> cloud -> LAN round trip
The LAN server exposes `POST /api/diagnostics/echo` and `GET /api/diagnostics/echo`
(`data/db/sarapp_db/api/routers/diagnostics.py`) — a no-op endpoint that
touches no database and simply echoes back whatever JSON body was sent, plus
a server-side UTC timestamp. Hit it through a connected tunnel:

```
curl -X POST https://<router-domain>/r/<connect_code>/api/diagnostics/echo \
     -H "Content-Type: application/json" -d '{"ping": "hello"}'
```

A response containing your posted body back, with a fresh `server_time_utc`,
confirms the full round trip: field device → cloud router → tunnel → LAN
server → back. The `GET` variant lets the same check be done from a plain
browser tab, including on a mobile device with no client beyond that. This
is a connectivity check only — no auth, no incident context — so a `200`
here proves the tunnel path is healthy, not that the LAN server's own
auth/session layer is.

## Env vars
| Variable | Set on | Purpose |
| --- | --- | --- |
| `SARAPP_CLOUD_ROUTER_URL` | LAN server | WebSocket URL of the cloud router's `/tunnel/register`. Unset = tunneling disabled, zero behavior change. |
| `SARAPP_CLOUD_ROUTER_TOKEN` | both | Shared secret for tunnel registration and the admin endpoints. |
| `SARAPP_CONNECT_CODE` | LAN server | Optional; auto-generated and logged if unset. |
| `SARAPP_ROUTER_REQUEST_TIMEOUT_SECONDS` | both (should match) | HTTP request/response timeout. Default 30. |
| `SARAPP_ROUTER_HEARTBEAT_INTERVAL_SECONDS` | router | How often the router pings each tunnel. Default 15. |
| `SARAPP_ROUTER_HEARTBEAT_TIMEOUT_SECONDS` | router | How long without a pong before a tunnel is considered dead. Default 45. |
| `SARAPP_ROUTER_MAX_PENDING_REQUESTS` | both | Per-tunnel concurrent in-flight request cap; also sizes the LAN client's own concurrency semaphore. Default 200. |
| `SARAPP_ROUTER_MAX_WS_CHANNELS` | router | Per-tunnel concurrent WS channel cap. Default 100. |
| `SARAPP_ROUTER_MAX_BODY_BYTES` | both | Max request body size before a `413`. Default 20MB. |
| `SARAPP_ROUTER_REGISTER_RATE_LIMIT` | router | Max `/tunnel/register` attempts per source IP per minute. Default 10. |

When the LAN server is launched through the SARApp Server Console
(`lan_server/server_console/`), the cloud router URL and connect code can also
be set in the console's Settings panel (persisted in `server_console.json`);
those values take precedence over the environment variables. The registration
token remains env-only (`SARAPP_CLOUD_ROUTER_TOKEN`) and is never persisted.
