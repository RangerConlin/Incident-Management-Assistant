"""MongoDB-backed GAR Template repository via SARApp API (master library)."""
from __future__ import annotations

from typing import Any


def _client():
    from utils.api_client import api_client

    return api_client


def list_gar_templates(include_inactive: bool = False) -> list[dict[str, Any]]:
    return _client().get("/api/gar-templates", params={"include_inactive": include_inactive}) or []


def get_gar_template(template_id: int) -> dict[str, Any]:
    return _client().get(f"/api/gar-templates/{template_id}")


def create_gar_template(payload: dict[str, Any]) -> dict[str, Any]:
    return _client().post("/api/gar-templates", json=payload)


def save_gar_template(template_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    return _client().put(f"/api/gar-templates/{template_id}", json=payload)


def clone_gar_template(template_id: int) -> dict[str, Any]:
    return _client().post(f"/api/gar-templates/{template_id}/clone")


def set_gar_template_active(template_id: int, active: bool) -> dict[str, Any]:
    return _client().patch(f"/api/gar-templates/{template_id}/active", json={"active": active})


def get_incident_default_gar_template(incident_id: str) -> int | None:
    result = _client().get(f"/api/incidents/{incident_id}/operations/gar-default-template")
    return (result or {}).get("template_id")


def set_incident_default_gar_template(incident_id: str, template_id: int | None) -> None:
    _client().patch(
        f"/api/incidents/{incident_id}/operations/gar-default-template",
        json={"template_id": template_id},
    )
