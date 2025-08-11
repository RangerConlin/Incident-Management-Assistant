"""Public Information module for ICS Command Assistant."""

from .api import router
from .models.repository import init_db


def register_api(app):
    """Register the module's FastAPI router."""
    app.include_router(router, prefix="/api/public_info")


def init_module(mission_id):
    """Ensure mission database has required tables."""
    init_db(mission_id)
