from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import APIRouter

from modules.plannedtoolkit import services, exporter
from modules.plannedtoolkit.models import schemas

router = APIRouter(prefix="/api/planned", tags=["planned"])


@router.get("/templates", response_model=List[schemas.EventTemplateRead])
def get_templates():
    return services.list_templates()


@router.post("/templates", response_model=schemas.EventTemplateRead)
def create_template(template: schemas.EventTemplateCreate):
    return services.create_template(template)


@router.post("/templates/{template_id}/clone")
def clone_template(template_id: int, req: schemas.CloneFromTemplateRequest | None = None):
    name = req.name if req else None
    event_id = services.clone_template(template_id, name)
    return {"event_id": event_id}


@router.get("/events")
def list_events():
    missions_dir = Path("data/missions")
    missions_dir.mkdir(parents=True, exist_ok=True)
    return {"events": [p.stem for p in missions_dir.glob("*.db")]}  # simple listing


@router.get("/events/{event_id}", response_model=schemas.EventRead | None)
def get_event(event_id: str):
    return services.get_event(event_id)


@router.get("/events/{event_id}/sites", response_model=List[schemas.EventSiteRead])
def list_sites(event_id: str):
    return services.list_sites(event_id)


@router.post("/events/{event_id}/sites", response_model=schemas.EventSiteRead)
def add_site(event_id: str, site: schemas.EventSiteCreate):
    return services.add_site(event_id, site)


@router.get("/events/{event_id}/routes", response_model=List[schemas.EventRouteRead])
def list_routes(event_id: str):
    return services.list_routes(event_id)


@router.post("/events/{event_id}/routes", response_model=schemas.EventRouteRead)
def add_route(event_id: str, route: schemas.EventRouteCreate):
    return services.add_route(event_id, route)


@router.post("/events/{event_id}/iap/build", response_model=schemas.ExportArtifactRead)
def build_iap(event_id: str, req: schemas.IapBuildRequest):
    artifact = exporter.export_iap(event_id, req)
    return schemas.ExportArtifactRead.from_orm(artifact)
