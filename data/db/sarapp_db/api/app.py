"""Shared SARApp FastAPI application.

All three server types (LAN standalone, cloud, built-in offline) import and
serve this app via uvicorn.  Module routers are registered here as they are
built out during the SQLite -> MongoDB cutover.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app(server_info_fn=None) -> FastAPI:
    """Create and configure the SARApp FastAPI application.

    Args:
        server_info_fn: Optional callable that returns a ServerInfo-compatible
            dict.  Each server type passes its own health/info payload function
            so /health reflects that server's live state.
    """
    app = FastAPI(
        title="SARApp API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -------------------------------------------------------------------------
    # Health / server-info (mirrors the old ThreadingHTTPServer endpoints)
    # -------------------------------------------------------------------------

    @app.get("/health")
    def health() -> dict[str, Any]:
        if server_info_fn is not None:
            return {"ok": True, "server": server_info_fn()}
        return {"ok": True}

    @app.get("/server-info")
    def server_info() -> dict[str, Any]:
        if server_info_fn is not None:
            return server_info_fn()
        return {}

    # -------------------------------------------------------------------------
    # Module routers (registered as each module is cut over to MongoDB)
    # -------------------------------------------------------------------------
    from sarapp_db.api.routers import objectives
    app.include_router(objectives.router, prefix="/api/objectives", tags=["objectives"])

    from sarapp_db.api.routers import hazard_types
    app.include_router(hazard_types.router, prefix="/api/hazard-types", tags=["hazard-types"])

    from sarapp_db.api.routers import resource_types
    app.include_router(resource_types.router, prefix="/api/resource-types", tags=["resource-types"])

    from sarapp_db.api.routers import ic_overview
    app.include_router(ic_overview.router, prefix="/api/incidents", tags=["incidents"])

    from sarapp_db.api.routers import incident_org
    app.include_router(incident_org.router, prefix="/api/incidents", tags=["incident-org"])

    return app
