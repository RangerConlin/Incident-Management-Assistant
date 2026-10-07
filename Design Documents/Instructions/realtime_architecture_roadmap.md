# Planned Real-Time Architecture

This is the intended post-cutover direction rather than a guarantee of what is already implemented.

- **IncidentCache**: client-side in-memory dict populated from a bounded server snapshot on incident load, then kept current by WebSocket push events. UI reads for active incident data should come from the cache by default; writes still go through the API so the server remains authoritative and broadcasts the resulting change.
- **Cache limits**: snapshots and live cache updates must obey collection/document limits so large incidents cannot consume unbounded RAM. Small active collections may be fully cached; heavy/history collections must be recent-only or paged. The snapshot endpoint returns metadata describing truncation.
- **CatalogCache**: separate client-side in-memory cache for stable master/global lookup data such as resource types, hazard types, organizations, rank structures, radio channel libraries, and task/team type catalogs. Invalidate it after catalog writes.
- **WebSocket hub**: FastAPI endpoint per incident at `/api/incidents/{incident_id}/ws` with generic collection change events.
- **Offline resilience (client ↔ its own local server, same LAN)**: each client runs a local MongoDB node as a replica set member. On disconnect, the client reads/writes locally; on reconnect, MongoDB replication resynchronizes the node. This assumes direct reachability between the client and its server, which holds on a LAN.
- **Implementation order**: finish MongoDB cutover -> add bounded `IncidentCache` + WebSocket broadcasts -> add `CatalogCache` for stable lookups -> configure local MongoDB replica -> replace HTTP reads with cache/catalog reads -> remove polling timers from status boards.

## Offline resilience (server ↔ central cloud master database)

A second, separate offline case exists between each LAN/cloud server's local
`sarapp_master` and the central `sarapp_central_master` database now embedded
in `cloud_router/` (see `cloud_router_architecture.md`). The mechanism above
does **not** apply directly here: a literal cross-WAN MongoDB replica set
needs direct reachability between members, but LAN servers dial *out*
through `cloud_router/`'s tunnel specifically because they are not
independently reachable (no inbound connectivity, dynamic IP/NAT) — that's
the whole reason the tunnel exists.

The chosen mechanism instead is **MongoDB change streams relayed over the
existing tunnel/API channel**: each LAN/cloud server watches its own local
`sarapp_master` collections via a change stream and relays deltas to/from the
central database through an authenticated endpoint, carrying change-stream
resume tokens end to end for ordering and replay-safety (not timestamp-based
ordering, which is vulnerable to clock skew). A per-server sync checkpoint
(last-applied resume token) is persisted so a reconnect after an outage
replays only the backlog, in both directions. This is Mongo-native in the
sense that it uses change streams rather than a hand-rolled diff/merge queue,
but it is explicitly **not** literal replica-set membership — flagged here so
the distinction from the client↔local-server case above isn't lost. Not yet
implemented; tracked in `backlog.md`.
