# SARApp Connectivity Architecture

SARApp remains a desktop-first PySide6 / Qt Widgets application. This phase adds a built-in local server startup path for users who launch the desktop app when no existing incident server is reachable. It does not redesign storage, migrate modules, replace SQLite behavior, add synchronization, or introduce QML.

## Startup Order

At launch, the desktop app uses `ConnectionManager` as the central place for connection state:

1. Try LAN/local discovery.
2. Try a configured cloud server.
3. If both fail, show the fallback prompt.

The connection snapshot reports one of the high-level states used by the rest of the app:

- `lan` for a LAN or same-machine local SARApp server.
- `cloud` for a configured cloud SARApp server.
- `offline` for desktop-only SQLite operation.
- `disconnected` before a successful connection or offline selection.

## Fallback Prompt

When no LAN server is found and the cloud server is unavailable, SARApp shows a plain Qt fallback prompt:

- **Start Local Incident Server**
- **Work Offline**
- **Retry Connection**
- **Manual Server Address**
- **Exit**

The prompt appears before the main window opens, so the app can start in a clear connection mode.

## Built-In Local Server Option

The **Start Local Incident Server** option uses `LocalServerController` in `core/networking/local_server_controller.py`. The controller:

- Checks whether `127.0.0.1:<default port>` already has a compatible SARApp `/health` endpoint.
- Treats an already-running compatible server as reusable and does not start a duplicate process.
- Detects when the port is occupied by a non-SARApp service and reports an error.
- Starts `sarapp_server.py` as a separate process with `sys.executable` in development mode.
- Waits for `/health` with a timeout.
- Tracks whether this desktop app started the process.
- Stops only the process it owns on application exit.

The local server advertises a simple SARApp-compatible health payload from `server/server_manager.py` at `/health`.

## LAN Server vs Local Server vs Offline

- **Connecting to a LAN server** means SARApp found or was pointed at an existing SARApp server and connected after `/health` succeeded. The desktop app does not own that process.
- **Starting a local server** means the desktop app launched the bundled server process on the same machine, waited for readiness, then connected to `127.0.0.1` through the same manual connection path used for other LAN/local servers.
- **Working offline** keeps the existing desktop SQLite behavior available without a network server.

## Manual Server Address

The manual fallback path accepts a host, `host:port`, or URL-like address. It validates the address by calling the server `/health` endpoint through `ConnectionManager.connect_manual`. Failed health checks return the user to the fallback prompt.

## Current Limitations

This phase is intentionally narrow:

- No server administration dashboard is included.
- No separate server console application is included.
- No sync, failover, election, or cloud management is implemented.
- Storage remains the current desktop SQLite behavior; this change does not migrate existing modules.
- The development startup command uses `sys.executable sarapp_server.py --host 127.0.0.1 --port <port> --name "Local SARApp Server"`. Future packaging can replace that command with a bundled executable without changing the startup flow.
