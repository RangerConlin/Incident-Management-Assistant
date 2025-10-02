"""Safety ORM module entry point."""

from __future__ import annotations

from fastapi import FastAPI

__all__ = ["register_api", "register_ui"]


def register_api(app: FastAPI) -> None:
    """Register FastAPI routes for the ORM module."""
    from .api import router as orm_router

    if not any(r.path.startswith("/api/safety/orm") for r in app.router.routes):
        app.include_router(orm_router)


def register_ui(menu_registry) -> None:
    """Register menu entry for the ORM window."""
    if menu_registry is None:
        return

    from .ui.orm_window import ORMWindow

    menu_registry.add_item(
        path="safety.cap_orm_singleton",
        title="CAP ORM (Per OP)",
        factory=lambda: ORMWindow(),
    )
