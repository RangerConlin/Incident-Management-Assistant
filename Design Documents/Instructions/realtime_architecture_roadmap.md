# Planned Real-Time Architecture

This is the intended post-cutover direction rather than a guarantee of what is already implemented.

- **IncidentCache**: client-side in-memory dict populated from a bounded server snapshot on incident load, then kept current by WebSocket push events. UI reads for active incident data should come from the cache by default; writes still go through the API so the server remains authoritative and broadcasts the resulting change.
- **Cache limits**: snapshots and live cache updates must obey collection/document limits so large incidents cannot consume unbounded RAM. Small active collections may be fully cached; heavy/history collections must be recent-only or paged. The snapshot endpoint returns metadata describing truncation.
- **CatalogCache**: separate client-side in-memory cache for stable master/global lookup data such as resource types, hazard types, organizations, rank structures, radio channel libraries, and task/team type catalogs. Invalidate it after catalog writes.
- **WebSocket hub**: FastAPI endpoint per incident at `/api/incidents/{incident_id}/ws` with generic collection change events.
- **Offline resilience (client ↔ its own local server, same LAN)**: each client runs a local MongoDB node as a replica set member. On disconnect, the client reads/writes locally; on reconnect, MongoDB replication resynchronizes the node. This assumes direct reachability between the client and its server, which holds on a LAN.
- **Implementation order**: finish MongoDB cutover -> add bounded `IncidentCache` + WebSocket broadcasts -> add `CatalogCache` for stable lookups -> configure local MongoDB replica -> replace HTTP reads with cache/catalog reads -> remove polling timers from status boards.

## Server ↔ central sync (server ↔ central cloud master database)

A second, separate offline case exists between each LAN/cloud server's local
`sarapp_master` and the central `sarapp_central_master` database embedded in
`cloud_router/` (see `cloud_router_architecture.md`). The client↔local-server
mechanism above does **not** apply here for two independent reasons:

1. A literal cross-WAN MongoDB replica set needs direct reachability between
   members, but LAN servers dial *out* through `cloud_router/`'s tunnel
   specifically because they are not independently reachable (no inbound
   connectivity, dynamic IP/NAT) — that's the whole reason the tunnel exists.
2. More fundamentally: **MongoDB change streams — the Mongo-native
   alternative to a full replica set considered here — still require every
   member to run as a replica set, even a single-node one.** Every
   deployment today (LAN server, cloud server, the built-in offline server)
   connects to a plain standalone `mongod`, confirmed by inspecting the
   deployment: `data/db/sarapp_db/mongo/mongo_client.py` makes a bare
   `MongoClient(uri)` with no `replicaSet=`, no LAN-server install/startup
   code provisions Mongo at all (it assumes a pre-existing local install),
   and `cloud_server/docker-compose.yml`'s `mongo: image: mongo:7` service
   has no `--replSet` command override. Requiring replica sets everywhere
   first would be an infrastructure migration, not a code change, and one
   with its own real costs (see the discussion that settled this: oplog
   retention means change streams still can't bridge a server that's been
   offline longer than the oplog window — exactly the SAR-team-laptop-off-
   for-weeks case this feature most needs to handle — so a full-resync
   fallback is required either way; the migration itself and its various
   footguns are also real work with no live fleet yet to justify rushing).

**Implemented mechanism: push-on-write with a local outbox**
(`data/db/sarapp_db/sync/`), not change streams. `BaseRepository` calls
`sync.relay.relay_local_write()` right after a write to a syncable master
collection (currently just `personnel` — see `sync.config.
SYNCABLE_MASTER_COLLECTIONS`) on a server's own local `sarapp_master`. That
attempts an immediate HTTP push to the central database's `/api/sync/push`
endpoint; on failure (offline, central down) the write is queued in a local
outbox (`sarapp_system.sync_state`) instead of being lost. A background
daemon thread (`sync.loop.CentralSyncLoop`, started by `lan_server/
server_manager.py` and `cloud_server/main.py`) periodically drains that
outbox and pulls anything changed centrally since each collection's last
checkpoint (`sarapp_system.sync_pull_checkpoints`) — this pull side is a
lightweight "what changed since X" query, not a poll of the whole
collection. Conflicts (existing record same-age-or-newer than an incoming
one, but content differs) resolve by last-write-wins and get logged to
`MasterCollections.SYNC_CONFLICTS` for review rather than silently merged.

This is intentionally simpler than change streams in exchange for needing
zero MongoDB reconfiguration: it works against every deployment as it
stands today. If sync latency (currently bounded by `CentralSyncLoop`'s
poll interval, default 60s — see `sync.config.sync_interval_seconds()`) ever
becomes an actual problem, change streams could be layered on top later as
a latency optimization for the common case, with this same push/outbox/pull
machinery remaining as the fallback for the long-offline case change streams
can't cover regardless.
