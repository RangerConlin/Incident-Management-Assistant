from __future__ import annotations

"""FastAPI router exposing ICS-203 incident helpers."""

from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from .controller import ICS203Controller
from .models import ensure_incident_schema, render_template

router = APIRouter(prefix="/command/ics203", tags=["ics203"])


@router.post("/{incident_id}/init", status_code=204)
def init_incident(incident_id: str) -> None:
    ensure_incident_schema(incident_id)


@router.get("/{incident_id}/units")
def list_units(incident_id: str) -> list[dict]:
    controller = ICS203Controller(incident_id)
    return [asdict(unit) for unit in controller.load_units()]


@router.get("/{incident_id}/positions")
def list_positions(incident_id: str) -> list[dict]:
    controller = ICS203Controller(incident_id)
    return [asdict(position) for position in controller.load_positions()]


@router.post("/{incident_id}/apply_template/{template_name}", status_code=204)
def apply_template(incident_id: str, template_name: str) -> None:
    controller = ICS203Controller(incident_id)
    items = render_template(template_name, incident_id)
    if not items:
        raise HTTPException(status_code=404, detail="Template not found")
    controller.apply_items(items)
