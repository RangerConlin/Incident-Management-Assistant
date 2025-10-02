"""FastAPI routes for the CAP ORM module."""

from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Query, Response, status
from fastapi.responses import JSONResponse, StreamingResponse

from . import pdf_export, service
from .validators import (
    ApproveRequest,
    FormRead,
    FormUpdate,
    HazardCreate,
    HazardRead,
    HazardUpdate,
)

router = APIRouter(prefix="/api/safety/orm", tags=["safety-orm"])


@router.get("/form", response_model=FormRead)
def get_form(incident_id: int = Query(...), op: int = Query(..., ge=1)) -> FormRead:
    form = service.ensure_form(incident_id, op)
    return FormRead.model_validate(form)


@router.put("/form", response_model=FormRead)
def update_form(payload: FormUpdate) -> FormRead:
    form = service.update_form_header(
        payload.incident_id,
        payload.op_period,
        payload.model_dump(exclude_unset=True),
    )
    return FormRead.model_validate(form)


@router.post("/approve", response_model=FormRead)
def approve(payload: ApproveRequest) -> Response:
    try:
        form = service.attempt_approval(payload.incident_id, payload.op_period)
    except service.ApprovalBlockedError as exc:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "approval_blocked",
                "reason": "highest_residual_risk_h_or_eh",
                "highest_residual_risk": exc.highest,
                "message": "Approval is blocked until highest residual risk is Medium or Low.",
            },
        )
    return FormRead.model_validate(form)


@router.get("/hazards", response_model=list[HazardRead])
def list_hazards(incident_id: int = Query(...), op: int = Query(..., ge=1)) -> list[HazardRead]:
    hazards = service.list_hazards(incident_id, op)
    return [HazardRead.model_validate(h) for h in hazards]


@router.post("/hazards", response_model=HazardRead, status_code=status.HTTP_201_CREATED)
def create_hazard(payload: HazardCreate) -> HazardRead:
    hazard = service.add_hazard(
        payload.incident_id, payload.op_period, payload.model_dump()
    )
    return HazardRead.model_validate(hazard)


@router.put("/hazards/{hazard_id}", response_model=HazardRead)
def update_hazard(
    hazard_id: int,
    payload: HazardUpdate,
    incident_id: int = Query(...),
    op: int = Query(..., ge=1),
) -> HazardRead:
    hazard = service.edit_hazard(
        incident_id, op, hazard_id, payload.model_dump()
    )
    return HazardRead.model_validate(hazard)


@router.delete("/hazards/{hazard_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_hazard(hazard_id: int, incident_id: int = Query(...), op: int = Query(..., ge=1)) -> Response:
    service.remove_hazard(incident_id, op, hazard_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/export")
def export_pdf(incident_id: int = Query(...), op: int = Query(..., ge=1)) -> StreamingResponse:
    form = service.ensure_form(incident_id, op)
    hazards = service.list_hazards(incident_id, op)
    pdf_bytes = pdf_export.build_pdf(form=form, hazards=hazards)
    filename = f"cap_orm_op{op}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )
