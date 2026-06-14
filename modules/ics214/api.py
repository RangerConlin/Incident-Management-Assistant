"""FastAPI router for ICS-214 endpoints."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from . import services
from .schemas import StreamCreate, StreamRead, StreamUpdate, EntryCreate, EntryRead, ExportRequest, ExportRead
from .ws import router as ws_router

router = APIRouter()
router.include_router(ws_router)

# Streams --------------------------------------------------------------------

@router.get("/streams", response_model=list[StreamRead])
def list_streams(incident_id: str):
    return services.list_streams(incident_id)

@router.post("/streams", response_model=StreamRead)
def create_stream(data: StreamCreate):
    return services.create_stream(data)

@router.put("/streams/{stream_id}", response_model=StreamRead | None)
def update_stream(incident_id: str, stream_id: str, data: StreamUpdate):
    return services.update_stream(incident_id, stream_id, data)

# Entries --------------------------------------------------------------------

@router.get("/streams/{stream_id}/entries", response_model=list[EntryRead])
def list_entries(incident_id: str, stream_id: str):
    return services.list_entries(incident_id, stream_id)

@router.post("/streams/{stream_id}/entries", response_model=EntryRead)
def add_entry(incident_id: str, stream_id: str, data: EntryCreate):
    return services.add_entry(incident_id, stream_id, data)

# Exports --------------------------------------------------------------------

@router.post("/streams/{stream_id}/export", response_model=ExportRead)
def export_stream(incident_id: str, stream_id: str, options: ExportRequest):
    exp = services.export_stream(incident_id, stream_id, options)
    return ExportRead(id=exp.id, file_path=exp.file_path, created_at=exp.created_at)

@router.get("/exports/{export_id}")
def download_export(incident_id: str, export_id: str):
    from utils.api_client import api_client
    try:
        doc = api_client.get(
            f"/api/incidents/{incident_id}/ics214/exports/{export_id}",
        )
        file_path = doc.get("file_path")
        if not file_path:
            return FileResponse("", status_code=404)
        return FileResponse(file_path)
    except Exception:
        return FileResponse("", status_code=404)
