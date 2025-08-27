# AUTO-GENERATED: Logistics module for Incident Management Assistant
# NOTE: Module code lives under /modules/logistics (not /backend).
"""FastAPI router for logistics module."""

from fastapi import APIRouter

from modules.logistics import services
from modules.logistics.models import (
    ResourceRequestCreate,
    ResourceRequestRead,
    RequestApprovalCreate,
    RequestAssignmentCreate,
    EquipmentItemCreate,
    EquipmentItemRead,
)
from .print_ics_213_rr import generate_pdf

router = APIRouter(tags=["logistics"])


@router.get("/requests", response_model=list[ResourceRequestRead])
def list_requests(incident_id: str):
    with services.with_incident_session(incident_id) as session:
        rows = session.query(services.LogisticsResourceRequest).all()
        return [ResourceRequestRead.from_orm(r) for r in rows]


@router.post("/requests", response_model=ResourceRequestRead)
def create_request_endpoint(incident_id: str, data: ResourceRequestCreate):
    req = services.create_request(incident_id, data)
    return ResourceRequestRead.from_orm(req)


@router.post("/requests/{request_id}/approve")
def approve_request_endpoint(
    incident_id: str, request_id: int, data: RequestApprovalCreate
):
    services.approve_request(incident_id, request_id, data)
    return {"status": "ok"}


@router.post("/requests/{request_id}/assign")
def assign_request_endpoint(
    incident_id: str, request_id: int, data: RequestAssignmentCreate
):
    services.assign_request(incident_id, request_id, data)
    return {"status": "ok"}


@router.get("/equipment", response_model=list[EquipmentItemRead])
def list_equipment(incident_id: str):
    with services.with_incident_session(incident_id) as session:
        rows = session.query(services.EquipmentItem).all()
        return [EquipmentItemRead.from_orm(r) for r in rows]


@router.post("/equipment", response_model=EquipmentItemRead)
def add_equipment_endpoint(incident_id: str, data: EquipmentItemCreate):
    item = services.add_equipment(incident_id, data)
    return EquipmentItemRead.from_orm(item)


@router.post("/equipment/{equipment_id}/checkout")
def checkout_equipment_endpoint(incident_id: str, equipment_id: int, actor_id: int):
    services.checkout_equipment(incident_id, equipment_id, actor_id)
    return {"status": "ok"}


@router.post("/equipment/{equipment_id}/checkin")
def checkin_equipment_endpoint(incident_id: str, equipment_id: int, actor_id: int):
    services.checkin_equipment(incident_id, equipment_id, actor_id)
    return {"status": "ok"}


@router.post("/requests/{request_id}/print/ics213rr")
def print_request(incident_id: str, request_id: int):
    path, _bytes = generate_pdf(incident_id, request_id)
    return {"path": path}
