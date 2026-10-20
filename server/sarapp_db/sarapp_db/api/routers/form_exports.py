"""HTTP boundary for the shared headless form export service."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from sarapp_db.form_exports.models import ExportError, ExportRequest
from sarapp_db.form_exports.service import default_service

router = APIRouter()
logger = logging.getLogger(__name__)
service = default_service()


class FormExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    form_id: str
    source_id: str | None = None
    operational_period_id: int | None = Field(default=None, gt=0)
    prepared_by: str = Field(default="", max_length=200)
    form_set_id: str | None = None
    prepared_by_position: str = Field(default="", max_length=200)


@router.get("/incidents/{incident_id}/form-exports")
def catalog(incident_id: str) -> list[dict]:
    return service.registry.catalog()


@router.post("/incidents/{incident_id}/form-exports")
def export_form(incident_id: str, body: FormExportRequest) -> Response:
    try:
        result = service.export(ExportRequest(incident_id=incident_id, **body.model_dump()))
    except ExportError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    except (ImportError, FileNotFoundError) as exc:
        logger.exception("Form export dependency or template unavailable")
        raise HTTPException(503, "Form export assets or PDF dependencies are unavailable on this server") from exc
    except ValueError as exc:
        logger.exception("Form export template validation failed")
        raise HTTPException(500, "The form template could not be filled safely") from exc
    return Response(result.content, media_type=result.media_type, headers={
        "Content-Disposition": f'attachment; filename="{result.filename}"',
        "Cache-Control": "no-store",
    })
