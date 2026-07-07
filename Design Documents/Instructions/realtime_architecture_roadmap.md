# Planned Real-Time Architecture

This is the intended post-cutover direction rather than a guarantee of what is already implemented.

- **IncidentCache**: client-side in-memory dict populated from a bounded server snapshot on incident load, then kept current by WebSocket push events. UI reads for active incident data should come from the cache by default; writes still go through the API so the server remains authoritative and broadcasts the resulting change.
- **Cache limits**: snapshots and live cache updates must obey collection/document limits so large incidents cannot consume unbounded RAM. Small active collections may be fully cached; heavy/history collections must be recent-only or paged. The snapshot endpoint returns metadata describing truncation.
- **CatalogCache**: separate client-side in-memory cache for stable master/global lookup data such as resource types, hazard types, organizations, rank structures, radio channel libraries, and task/team type catalogs. Invalidate it after catalog writes.
- **WebSocket hub**: FastAPI endpoint per incident at `/api/incidents/{incident_id}/ws` with generic collection change events.
- **Offline resilience**: each client runs a local MongoDB node as a replica set member. On disconnect, the client reads/writes locally; on reconnect, MongoDB replication resynchronizes the node.
- **Implementation order**: finish MongoDB cutover -> add bounded `IncidentCache` + WebSocket broadcasts -> add `CatalogCache` for stable lookups -> configure local MongoDB replica -> replace HTTP reads with cache/catalog reads -> remove polling timers from status boards.
