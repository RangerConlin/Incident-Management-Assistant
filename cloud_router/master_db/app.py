"""Builds the central master-catalog sub-app mounted into cloud_router.

This module never implements its own Mongo access or master-data routers —
it reuses ``sarapp_db.api.app.create_app(mode="master_only")`` verbatim,
exactly like ``cloud_server`` reuses the full ``create_app()``. The only
thing specific to cloud_router is pointing that shared app at cloud_router's
own Mongo instance (``SARAPP_CLOUD_ROUTER_MONGO_URI``) and at the
``sarapp_central_master`` database name instead of each server's local
``sarapp_master``. It then adds one thing cloud_router *does* own:
``master_db.webgui``'s browser-based CRUD GUI at ``/gui/...`` (so,
``/central-master/gui/...`` once mounted) — the GUI itself still calls the
same master-router functions, never Mongo directly.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI

logger = logging.getLogger(__name__)

_ROUTER_MONGO_URI_ENV_VAR = "SARAPP_CLOUD_ROUTER_MONGO_URI"


def create_master_app() -> FastAPI | None:
    """Create the central master-catalog FastAPI app, or None if unconfigured.

    Returns None (and logs a warning) when ``SARAPP_CLOUD_ROUTER_MONGO_URI``
    is not set, so cloud_router can still start as a plain stateless proxy in
    environments that haven't opted into the embedded master database yet.
    """
    mongo_uri = os.environ.get(_ROUTER_MONGO_URI_ENV_VAR, "").strip()
    if not mongo_uri:
        logger.info(
            "%s not set — cloud_router starting without the embedded central "
            "master database.",
            _ROUTER_MONGO_URI_ENV_VAR,
        )
        return None

    # sarapp_db's Mongo client and master-DB name resolution are both
    # env-var-driven (SARAPP_MONGO_URI, SARAPP_MASTER_DB_NAME) so no router or
    # repository code needs to change to serve the central catalog instead of
    # a server's local one. These must be set before sarapp_db is imported
    # anywhere in this process.
    os.environ["SARAPP_MONGO_URI"] = mongo_uri
    os.environ.setdefault("SARAPP_MASTER_DB_NAME", "sarapp_central_master")

    from sarapp_db.api.app import create_app

    logger.info("Central master database enabled (mode=master_only).")
    app = create_app(mode="master_only")

    from master_db.webgui import create_master_gui_router

    app.include_router(create_master_gui_router())
    return app
