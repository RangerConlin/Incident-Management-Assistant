"""Hosted SARApp cloud server entry point.

This replaces the former stateless reverse-tunnel router. The hosted cloud
server is a LAN-server-equivalent backend running on a VPS: it serves the
normal SARApp API under the same connect-code URL shape clients already use.
"""

from __future__ import annotations

import logging
import os

import uvicorn

from cloud_server.config import load_settings
from cloud_server.dashboard import create_dashboard_router
from cloud_server.prefix import ConnectCodePrefixMiddleware
from cloud_server.runtime import RequestLog, RuntimeLogHandler, ServerRuntime
from cloud_server.tunnel_client import (
    CloudTunnelClient,
    get_cloud_router_token,
    get_cloud_router_url,
)
from sarapp_db.api.app import create_app
from sarapp_db.sync.config import derive_central_master_url
from sarapp_db.sync.loop import CentralSyncLoop


def create_cloud_app():
    settings = load_settings()
    runtime = ServerRuntime(
        server_id=settings.server_id,
        server_name=settings.server_name,
        connect_code=settings.connect_code,
        requests=RequestLog(limit=settings.request_log_limit),
    )
    app = create_app(
        server_info_fn=runtime.server_info,
        request_log_fn=runtime.requests.append,
    )
    log_handler = RuntimeLogHandler(runtime.logs)
    logging.getLogger().addHandler(log_handler)
    logging.getLogger().setLevel(logging.INFO)
    app.state.cloud_log_handler = log_handler
    app.include_router(create_dashboard_router(settings, runtime))
    app.add_middleware(ConnectCodePrefixMiddleware, connect_code=settings.connect_code)

    cloud_router_url = get_cloud_router_url()
    tunnel_client = CloudTunnelClient(
        local_port=8000,
        server_id=settings.server_id,
        server_name=settings.server_name,
        cloud_router_url=cloud_router_url,
        token=get_cloud_router_token(),
        connect_code=settings.connect_code,
    )
    app.state.cloud_tunnel_client = tunnel_client

    # The central catalog lives inside cloud_router itself — there is no
    # separate URL to configure for it. Derive SARAPP_CENTRAL_MASTER_URL
    # from the same cloud_router_url this server already uses for its
    # tunnel (see sarapp_db.sync.config.derive_central_master_url).
    # No-ops entirely when that's unset, so starting the loop
    # unconditionally costs nothing for deployments with no tunnel — see
    # Design Documents/Instructions/cloud_router_architecture.md.
    derived_central_master_url = derive_central_master_url(cloud_router_url)
    if derived_central_master_url:
        os.environ["SARAPP_CENTRAL_MASTER_URL"] = derived_central_master_url
    central_sync_loop = CentralSyncLoop()
    app.state.central_sync_loop = central_sync_loop

    @app.on_event("startup")
    def _start_cloud_router_tunnel() -> None:
        tunnel_client.start()
        central_sync_loop.start()

    @app.on_event("shutdown")
    def _stop_cloud_router_tunnel() -> None:
        tunnel_client.stop()
        central_sync_loop.stop()
        logging.getLogger().removeHandler(log_handler)

    return app


app = create_cloud_app()


def main() -> int:
    uvicorn.run("cloud_server.main:app", host="0.0.0.0", port=8000, proxy_headers=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

