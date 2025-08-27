from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from modules.public_info.models.repository import PublicInfoRepository
from modules.public_info.models.schemas import (
    MessageCreate,
    MessageList,
    MessageRead,
    MessageUpdate,
)

router = APIRouter()


# Dependency helpers -------------------------------------------------------

def get_current_user():
    """Stub current user; replace with real auth integration."""
    return {"id": 1, "roles": ["PIO", "LeadPIO"]}


def get_repo(incident_id: str = "1"):  # incident id would come from app state
    return PublicInfoRepository(incident_id)


# Routes -------------------------------------------------------------------

@router.get("/messages", response_model=list[MessageRead])
def list_messages(
    status: Optional[str] = None,
    type: Optional[str] = None,
    audience: Optional[str] = None,
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    repo: PublicInfoRepository = Depends(get_repo),
):
    return repo.list_messages(
        status=status, type=type, audience=audience, q=q, page=page, page_size=page_size
    )


@router.post("/messages", response_model=MessageRead)
def create_message(
    payload: MessageCreate,
    repo: PublicInfoRepository = Depends(get_repo),
    user: dict = Depends(get_current_user),
):
    data = payload.dict()
    data["created_by"] = user["id"]
    return repo.create_message(data)


@router.get("/messages/{message_id}", response_model=MessageRead)
def get_message(message_id: int, repo: PublicInfoRepository = Depends(get_repo)):
    msg = repo.get_message(message_id)
    if not msg:
        raise HTTPException(404, "Message not found")
    return msg


@router.put("/messages/{message_id}", response_model=MessageRead)
def update_message(
    message_id: int,
    payload: MessageUpdate,
    repo: PublicInfoRepository = Depends(get_repo),
    user: dict = Depends(get_current_user),
):
    return repo.update_message(message_id, payload.dict(exclude_unset=True), user["id"])


@router.post("/messages/{message_id}/submit", response_model=MessageRead)
def submit_for_review(
    message_id: int,
    repo: PublicInfoRepository = Depends(get_repo),
    user: dict = Depends(get_current_user),
):
    return repo.submit_for_review(message_id, user["id"])


@router.post("/messages/{message_id}/approve", response_model=MessageRead)
def approve_message(
    message_id: int,
    repo: PublicInfoRepository = Depends(get_repo),
    user: dict = Depends(get_current_user),
):
    return repo.approve_message(message_id, user)


@router.post("/messages/{message_id}/publish", response_model=MessageRead)
def publish_message(
    message_id: int,
    repo: PublicInfoRepository = Depends(get_repo),
    user: dict = Depends(get_current_user),
):
    return repo.publish_message(message_id, user)


@router.post("/messages/{message_id}/archive", response_model=MessageRead)
def archive_message(
    message_id: int,
    repo: PublicInfoRepository = Depends(get_repo),
    user: dict = Depends(get_current_user),
):
    return repo.archive_message(message_id, user["id"])


@router.get("/history", response_model=list[MessageRead])
def history(repo: PublicInfoRepository = Depends(get_repo)):
    return repo.list_history()


@router.get("/export/{message_id}.pdf")
def export_pdf(
    message_id: int,
    repo: PublicInfoRepository = Depends(get_repo),
):
    msg = repo.get_message(message_id)
    if not msg:
        raise HTTPException(404, "Message not found")
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    textobject = c.beginText(40, 750)
    textobject.textLine(f"Title: {msg['title']}")
    textobject.textLine(f"Type: {msg['type']} Audience: {msg['audience']}")
    textobject.textLine("")
    for line in msg["body"].splitlines():
        textobject.textLine(line)
    c.drawText(textobject)
    c.showPage()
    c.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf")
