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
def list_streams(mission_id: str):
    return services.list_streams(mission_id)

@router.post("/streams", response_model=StreamRead)
def create_stream(data: StreamCreate):
    return services.create_stream(data)

@router.put("/streams/{stream_id}", response_model=StreamRead | None)
def update_stream(mission_id: str, stream_id: str, data: StreamUpdate):
    return services.update_stream(mission_id, stream_id, data)

# Entries --------------------------------------------------------------------

@router.get("/streams/{stream_id}/entries", response_model=list[EntryRead])
def list_entries(mission_id: str, stream_id: str):
    return services.list_entries(mission_id, stream_id)

@router.post("/streams/{stream_id}/entries", response_model=EntryRead)
def add_entry(mission_id: str, stream_id: str, data: EntryCreate):
    return services.add_entry(mission_id, stream_id, data)

# Exports --------------------------------------------------------------------

@router.post("/streams/{stream_id}/export", response_model=ExportRead)
def export_stream(mission_id: str, stream_id: str, options: ExportRequest):
    exp = services.export_stream(mission_id, stream_id, options)
    return ExportRead(id=exp.id, file_path=exp.file_path, created_at=exp.created_at)

@router.get("/exports/{export_id}")
def download_export(mission_id: str, export_id: str):
    # Simple lookup and file serving
    from modules._infra.repository import with_mission_session
    from .models import ICS214Export
    with with_mission_session(mission_id) as session:
        exp = session.get(ICS214Export, export_id)
        if not exp:
            return FileResponse("", status_code=404)
        return FileResponse(exp.file_path)
