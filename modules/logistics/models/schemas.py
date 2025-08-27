# AUTO-GENERATED: Logistics module for Incident Management Assistant
# NOTE: Module code lives under /modules/logistics (not /backend).
"""Pydantic schemas for logistics module."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ResourceRequestCreate(BaseModel):
    requestor_id: int
    item_code: str
    quantity: int
    priority: str
    justification: Optional[str] = None
    due_datetime: Optional[datetime] = None
    notes: Optional[str] = None


class ResourceRequestRead(ResourceRequestCreate):
    id: int
    incident_id: str
    status: str
    timestamp: datetime

    class Config:
        orm_mode = True


class RequestApprovalCreate(BaseModel):
    approver_id: int
    action: str
    comments: Optional[str] = None


class RequestAssignmentCreate(BaseModel):
    resource_id: Optional[int] = None
    assigned_to_id: Optional[int] = None
    eta: Optional[datetime] = None
    status: Optional[str] = "pending"


class EquipmentItemCreate(BaseModel):
    name: str
    type_id: Optional[str] = None
    serial_number: Optional[str] = None
    location: Optional[str] = None


class EquipmentItemRead(EquipmentItemCreate):
    id: int
    status: str
    current_holder_id: Optional[int]

    class Config:
        orm_mode = True


class PermissionOut(BaseModel):
    can_create: bool = False
    can_approve: bool = False
    can_assign: bool = False
    can_finalize: bool = False
