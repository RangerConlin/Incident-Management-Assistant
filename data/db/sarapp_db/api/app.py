"""Shared SARApp FastAPI application.

All three server types (LAN standalone, cloud, built-in offline) import and
serve this app via uvicorn.  Module routers are registered here as they are
built out during the SQLite -> MongoDB cutover.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# Header the cloud router stamps with the real field-device IP before
# forwarding a request down the reverse tunnel (see
# cloud_server/router/app.py). Only trusted when the request actually
# arrived over the tunnel's loopback hop (client.host == 127.0.0.1) — a
# direct LAN client could otherwise set this header itself to spoof another
# address in the traffic log.
_TUNNEL_CLIENT_IP_HEADER = "x-sarapp-client-ip"
_LOOPBACK_HOST = "127.0.0.1"


def _client_address(request: Request) -> str:
    host = request.client.host if request.client else ""
    if host == _LOOPBACK_HOST:
        forwarded = request.headers.get(_TUNNEL_CLIENT_IP_HEADER)
        if forwarded:
            return forwarded
    return host


def create_app(server_info_fn=None, request_log_fn=None) -> FastAPI:
    """Create and configure the SARApp FastAPI application.

    Args:
        server_info_fn: Optional callable that returns a ServerInfo-compatible
            dict.  Each server type passes its own health/info payload function
            so /health reflects that server's live state.
        request_log_fn: Optional callable receiving one dict per completed
            HTTP request (timestamp, client, method, path, query, status,
            duration_ms).  Used by the LAN server console's API traffic tab.
            Must be fast and non-raising; WebSocket traffic is not captured.
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

    if request_log_fn is not None:

        @app.middleware("http")
        async def _record_api_traffic(request: Request, call_next):
            started = time.perf_counter()
            response = await call_next(request)
            try:
                request_log_fn(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "client": _client_address(request),
                        "method": request.method,
                        "path": request.url.path,
                        "query": request.url.query,
                        "status": response.status_code,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    }
                )
            except Exception:  # noqa: BLE001 - logging must never break requests
                pass
            return response

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
    from sarapp_db.api.routers import auth_sessions
    from sarapp_db.api.routers import audit
    from sarapp_db.api.routers import notifications
    from sarapp_db.api.routers import diagnostics
    from sarapp_db.api.routers import client_connections
    from sarapp_db.api.routers import push_tokens
    from sarapp_db.api.routers import mobile_location
    app.include_router(objectives.router, prefix="/api/objectives", tags=["objectives"])
    app.include_router(auth_sessions.router, prefix="/api/auth", tags=["auth"])
    app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
    app.include_router(notifications.router, prefix="/api", tags=["notifications"])
    app.include_router(diagnostics.router, prefix="/api/diagnostics", tags=["diagnostics"])
    app.include_router(client_connections.router, prefix="/api/client-connections", tags=["client-connections"])
    app.include_router(push_tokens.router, prefix="/api/mobile", tags=["mobile"])
    app.include_router(mobile_location.router, prefix="/api/mobile", tags=["mobile"])

    from sarapp_db.api.routers import hazard_types
    app.include_router(hazard_types.router, prefix="/api/hazard-types", tags=["hazard-types"])

    from sarapp_db.api.routers import resource_types
    app.include_router(resource_types.router, prefix="/api/resource-types", tags=["resource-types"])

    from sarapp_db.api.routers import ic_overview
    app.include_router(ic_overview.router, prefix="/api/incidents", tags=["incidents"])

    from sarapp_db.api.routers import incident_org
    app.include_router(incident_org.router, prefix="/api/incidents", tags=["incident-org"])

    from sarapp_db.api.routers import lookup_types
    app.include_router(lookup_types.router, prefix="/api/lookup", tags=["lookup-types"])

    from sarapp_db.api.routers import communications
    app.include_router(communications.master_router, prefix="/api/comms", tags=["communications"])
    app.include_router(communications.incident_router, prefix="/api", tags=["communications"])

    from sarapp_db.api.routers import public_information
    app.include_router(public_information.router, prefix="/api", tags=["public-information"])

    from sarapp_db.api.routers import forms
    app.include_router(forms.master_router, prefix="/api/forms", tags=["forms"])
    app.include_router(forms.incident_router, prefix="/api", tags=["forms"])

    from sarapp_db.api.routers import ics214
    app.include_router(ics214.router, prefix="/api", tags=["ics214"])

    from sarapp_db.api.routers import initialresponse
    app.include_router(initialresponse.router, prefix="/api", tags=["initialresponse"])

    from sarapp_db.api.routers import plannedtoolkit
    app.include_router(plannedtoolkit.router, prefix="/api", tags=["planned-toolkit"])

    from sarapp_db.api.routers import intel
    app.include_router(intel.router, prefix="/api", tags=["intel"])

    from sarapp_db.api.routers import weather
    app.include_router(weather.router, prefix="/api", tags=["weather"])
    from sarapp_db.api.routers import geocoding
    app.include_router(geocoding.router, prefix="/api/geocoding", tags=["geocoding"])

    from sarapp_db.api.routers import safety
    app.include_router(safety.router, prefix="/api", tags=["safety"])

    from sarapp_db.api.routers import liaison
    app.include_router(liaison.router, prefix="/api", tags=["liaison"])

    from sarapp_db.api.routers import liaison_reporting
    app.include_router(liaison_reporting.router, prefix="/api", tags=["liaison"])

    from sarapp_db.api.routers import liaison_requests
    app.include_router(liaison_requests.router, prefix="/api", tags=["liaison"])

    from sarapp_db.api.routers import resource_status as resource_status_router
    app.include_router(
        resource_status_router.router,
        prefix="/api/incidents/{incident_id}/resource-status",
        tags=["resource-status"],
    )

    from sarapp_db.api.routers import logistics_resource_requests
    app.include_router(logistics_resource_requests.router, prefix="/api", tags=["logistics"])

    from sarapp_db.api.routers import operations
    app.include_router(operations.router, prefix="/api", tags=["operations"])

    from sarapp_db.api.routers import operational_periods
    app.include_router(operational_periods.router, prefix="/api", tags=["planning"])

    from sarapp_db.api.routers import meetings
    app.include_router(meetings.master_router, prefix="/api/master/meeting-templates", tags=["planning"])
    app.include_router(meetings.incident_router, prefix="/api", tags=["planning"])
    from sarapp_db.api.routers import facilities
    app.include_router(facilities.router, prefix="/api", tags=["facilities"])

    from sarapp_db.api.routers import work_assignments
    app.include_router(work_assignments.router, prefix="/api", tags=["planning"])

    from sarapp_db.api.routers import gis
    app.include_router(gis.router, prefix="/api", tags=["gis"])

    from sarapp_db.api.routers import finance
    app.include_router(finance.router, prefix="/api", tags=["finance"])

    from sarapp_db.api.routers import objective_templates
    app.include_router(objective_templates.router, prefix="/api/master/objective-templates", tags=["planning"])

    from sarapp_db.api.routers import strategy_templates
    app.include_router(strategy_templates.router, prefix="/api/master/strategy-templates", tags=["planning"])

    from sarapp_db.api.routers import aircraft
    app.include_router(aircraft.router, prefix="/api/master/aircraft", tags=["logistics"])

    from sarapp_db.api.routers import vehicles
    app.include_router(vehicles.router, prefix="/api/master/vehicles", tags=["logistics"])

    from sarapp_db.api.routers import personnel
    app.include_router(personnel.router, prefix="/api/master/personnel", tags=["logistics"])

    from sarapp_db.api.routers import equipment
    app.include_router(equipment.router, prefix="/api/master/equipment", tags=["logistics"])

    from sarapp_db.api.routers import hospitals
    app.include_router(hospitals.router, prefix="/api/master/hospitals", tags=["medical"])

    from sarapp_db.api.routers import medical
    app.include_router(medical.router, prefix="/api", tags=["medical"])

    from sarapp_db.api.routers import checkin
    app.include_router(checkin.router, prefix="/api/incidents/{incident_id}/checkin", tags=["logistics"])

    from sarapp_db.api.routers import incident_resources
    app.include_router(incident_resources.router, prefix="/api/incidents/{incident_id}/resources", tags=["logistics"])

    from sarapp_db.api.routers import certifications
    app.include_router(certifications.router, prefix="/api/master/certifications", tags=["personnel"])

    from sarapp_db.api.routers import organizations
    app.include_router(organizations.router, prefix="/api/master", tags=["personnel"])

    from sarapp_db.api.routers import reference_library
    from sarapp_db.api.routers import approvals
    app.include_router(reference_library.router, prefix="/api/master/reference-library", tags=["reference-library"])
    app.include_router(approvals.router, prefix="/api", tags=["approvals"])

    from sarapp_db.api.routers import attachments
    app.include_router(attachments.router, prefix="/api", tags=["attachments"])

    from sarapp_db.api.routers import task_narratives
    app.include_router(task_narratives.router, prefix="/api", tags=["narratives"])

    from sarapp_db.api.routers import iap
    app.include_router(iap.router, prefix="/api", tags=["iap"])

    from sarapp_db.api.routers import safety_templates
    app.include_router(safety_templates.router, prefix="/api/master/safety-templates", tags=["safety"])

    from sarapp_db.api.routers import canned_comm_entries
    app.include_router(canned_comm_entries.router, prefix="/api/master/canned-comm-entries", tags=["communications"])

    from sarapp_db.api.routers import incident_stream
    app.include_router(incident_stream.router, prefix="/api", tags=["incident-cache"])

    from sarapp_db.api.routers import sitrep
    app.include_router(sitrep.router, prefix="/api", tags=["sitrep"])

    from sarapp_db.api.routers import chat
    app.include_router(chat.router, prefix="/api", tags=["chat"])

    return app
