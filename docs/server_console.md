# SARApp Server Console

The SARApp Server Console is a lightweight PySide6 / Qt Widgets control panel for running and monitoring a SARApp incident server on a dedicated laptop, mini PC, EOC workstation, or future appliance-style deployment. It is separate from the full SARApp desktop client and does not include incident boards, forms, planning tools, operations modules, or the normal workspace menus.

## Entry points

SARApp now has separate launch paths:

```bash
python main.py
python sarapp_server.py --host 0.0.0.0 --port 8765 --name "Incident Server"
python sarapp_server_console.py
```

Use `main.py` for the desktop client. Use `sarapp_server.py` for a terminal-driven server. Use `sarapp_server_console.py` when a machine should behave like a server control panel without requiring terminal interaction.

## What the console controls

The console reuses the existing server runtime in `server/server_manager.py` and the networking primitives in `core/networking/`. It starts the same HTTP health server and UDP discovery broadcaster used by the command-line server. It does not duplicate the server implementation or redesign storage.

The window shows:

- Server status: stopped, starting, running, stopping, error, or monitoring.
- Server name, host, port, server ID, version, started time, and discovery status.
- Start, stop, restart, copy-address, and health-check actions.
- Basic persistent settings.
- A placeholder client-connections table for future connected-client metadata.
- Runtime log and error messages.

## Settings

Console settings are saved in:

```text
settings/server_console.json
```

Default settings are:

```json
{
  "server_name": "SARApp Incident Server",
  "host": "0.0.0.0",
  "port": 8765,
  "discovery_enabled": true
}
```

`server_name` is advertised to LAN clients. `host` controls the interface the HTTP server binds to; `0.0.0.0` listens on all interfaces. `port` is the HTTP health/server-info port and must be between 1 and 65535. `discovery_enabled` controls whether UDP LAN discovery broadcasts are sent while the server is running. `discovery_port` is available for networks that need a non-default UDP discovery port.

Saving settings while the server is running does not silently rebind the server. The new values apply on the next start, or immediately after using Restart Server.

## LAN discovery

When discovery is enabled, the server sends UDP announcements containing its server ID, name, version, status, host, port, and heartbeat timestamp. SARApp desktop clients use those broadcasts to find the server automatically on the same LAN. If a network blocks broadcast traffic, clients can still use manual connection workflows.

## Port conflict behavior

Before starting a server, the console checks the configured port. If `/health` responds with a SARApp-compatible payload, the console warns that a SARApp server is already running and can monitor that server instead of starting a second copy. If the port is used by another service, the console shows an error and does not start the SARApp server.

## Health monitoring

The console periodically calls `/health` with a short timeout while running or monitoring. It displays Healthy, Error, or Stopped and logs only state changes or errors so routine successful health checks do not spam the log panel.

## Troubleshooting

- **Port unavailable:** Choose a different port or stop the service already using the configured port.
- **Desktop client cannot discover the server:** Confirm discovery is enabled, both machines are on the same LAN, and local firewall rules allow UDP discovery traffic.
- **Health check fails:** Confirm the configured host/port are correct and that the server status is Running.
- **Settings did not affect a running server:** Use Restart Server after saving settings.
