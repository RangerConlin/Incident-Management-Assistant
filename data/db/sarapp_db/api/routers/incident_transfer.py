"""Export/import a whole incident as a single portable file.

See sarapp_db.export_import for the package format and the actual
build/restore logic — this router is just the HTTP surface over it.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import Response

from sarapp_db.export_import.exporter import build_incident_export
from sarapp_db.export_import.importer import ImportFormatError, import_incident_export
from sarapp_db.mongo.errors import RepositoryError

router = APIRouter()


@router.get("/incidents/{incident_id}/export")
def export_incident(incident_id: str) -> Response:
    try:
        filename, data = build_incident_export(incident_id)
    except RepositoryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/incidents/import", status_code=201)
async def import_incident(
    file: UploadFile,
    number: str = Form(...),
    name: str = Form(...),
) -> dict[str, Any]:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    try:
        return import_incident_export(data, number=number, name=name)
    except ImportFormatError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
