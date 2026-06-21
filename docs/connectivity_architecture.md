# SARApp Connectivity Architecture (Phase 1)

SARApp and ICS Command Assistant are the same desktop-first PySide6 project. This phase adds the networking foundation only: discovery, connection state management, heartbeats, and server health checks. It does not change database storage, add MongoDB, introduce QML, or migrate incident modules.

## Launch Connection Workflow

When SARApp starts, `main.py` creates a centralized `ConnectionManager` and runs the startup connection flow before the main workspace is shown:

1. Search the local LAN for SARApp Server announcements.
2. If a server is discovered, connect to that LAN server automatically.
3. If no LAN server is found, try the configured cloud URL (`SARAPP_CLOUD_URL`).
4. If cloud is unavailable, prompt the user to enter Offline Mode.

`SARAPP_CONNECTIVITY_DISABLED=1` can disable this startup workflow for troubleshooting or specialized test runs.

## LAN Discovery Process

Phase 1 uses UDP broadcast rather than cloud services, DNS, or manual IP entry as the primary discovery mechanism. A SARApp Server periodically sends a JSON announcement to the local broadcast domain. The payload contains:

- Server ID
- Server name
- Version
- Status
- Host and port
- Last heartbeat timestamp
- Future failover fields (`connected_timestamp`, `last_synchronization_timestamp`)

Broadcast is intentionally simple for incident networks where laptops are commonly connected to the same router or access point. If a network blocks broadcast, clients can still use manual connection fallback through the same `ConnectionManager` API.

## SARApp Server Health Endpoints

`server/server_manager.py` provides a minimal phase-1 server runtime using the Python standard library. It exposes:

- `GET /health` for connection checks.
- `GET /server-info` for server metadata.
- UDP discovery announcements through `DiscoveryBroadcaster`.

This is not a data API and does not perform database work. Future server implementations can replace or extend it while preserving the advertised `ServerInfo` contract.

A server can be started with:

```bash
python sarapp_server.py --host 0.0.0.0 --port 8765 --name "Incident Command Server"
```

Dedicated server machines can also launch the PySide6 Qt Widgets Server Console:

```bash
python sarapp_server_console.py
```

The Server Console is a control panel for starting, stopping, monitoring, and configuring the same `SARAppServerManager` runtime. It is not a second desktop client and does not load incident workspace modules.

## Heartbeat Mechanism

The same UDP announcement acts as a heartbeat. Clients record the latest heartbeat in `HeartbeatTracker` and derive connection health from heartbeat freshness:

- `healthy`: heartbeat was observed within the timeout window.
- `stale`: the known server has not been heard from recently.
- `unknown`: no heartbeat record exists.
- `disconnected`: no active connection exists.

The heartbeat framework is intentionally separate from persistence so later failover and synchronization logic can be added without redesigning discovery.

## Offline Mode Behavior

Offline Mode is a first-class connection state, not an error. The connection manager exposes it as:

- `ConnectionState.OFFLINE`
- `ConnectionMode.OFFLINE`

The launch workflow only prompts for Offline Mode after LAN discovery and cloud connection attempts fail. Existing single-computer workflows can continue to operate while future modules can inspect the connection snapshot to decide whether network synchronization is available.

## Future Failover Preparation

`ServerInfo` already includes the fields needed for the future strategy:

- `server_id`
- `connected_timestamp`
- `last_heartbeat`
- `last_synchronization_timestamp`

The planned failover rule is **Oldest Connected Synchronized Server Wins**. Election and failover behavior are intentionally not implemented in this phase. The current code only records the metadata needed to support that future decision.

## Architectural Decisions

- **Central manager:** All connection decisions are made through `ConnectionManager`, keeping incident modules independent from discovery/cloud/offline details.
- **UDP broadcast discovery:** Chosen for no-cloud LAN operation and minimal user configuration.
- **HTTP health checks:** Chosen as a lightweight connection confirmation path that future API servers can preserve.
- **No storage redesign:** Connectivity metadata remains in memory for phase 1.
- **No QML:** The startup prompt uses existing PySide6 widgets.
