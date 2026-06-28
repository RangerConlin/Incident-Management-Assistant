# Planned Real-Time Architecture

This is the intended post-cutover direction rather than a guarantee of what is already implemented.

- **IncidentCache**: client-side in-memory dict populated from a server snapshot on incident load, then kept current by WebSocket push events. UI reads come from the cache.
- **WebSocket hub**: FastAPI endpoint per incident at `/ws/incidents/{incident_id}` with typed change events such as `team_status_changed` or `task_updated`.
- **Offline resilience**: each client runs a local MongoDB node as a replica set member. On disconnect, the client reads/writes locally; on reconnect, MongoDB replication resynchronizes the node.
- **Implementation order**: finish MongoDB cutover -> add `IncidentCache` + WebSocket broadcasts -> configure local MongoDB replica -> replace HTTP reads with cache reads -> remove polling timers from status boards.
