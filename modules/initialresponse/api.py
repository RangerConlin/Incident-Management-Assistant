from __future__ import annotations

from fastapi import APIRouter

from .models import (
    HastyTaskCreate,
    HastyTaskRead,
    ReflexActionCreate,
    ReflexActionRead,
)
from . import services

router = APIRouter(prefix="/api/initialresponse", tags=["initialresponse"])


@router.get("/hasty", response_model=list[HastyTaskRead])
def list_hasty_tasks() -> list[HastyTaskRead]:
    return services.list_hasty_task_entries()


@router.post("/hasty", response_model=HastyTaskRead)
def create_hasty_task(payload: HastyTaskCreate) -> HastyTaskRead:
    return services.create_hasty_task(payload)


@router.get("/reflex", response_model=list[ReflexActionRead])
def list_reflex_actions() -> list[ReflexActionRead]:
    return services.list_reflex_action_entries()


@router.post("/reflex", response_model=ReflexActionRead)
def create_reflex_action(payload: ReflexActionCreate) -> ReflexActionRead:
    return services.create_reflex_action(payload)


__all__ = ["router"]
