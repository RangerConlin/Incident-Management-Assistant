# AUTO-GENERATED: Logistics module for Incident Management Assistant
# NOTE: Module code lives under /modules/logistics (not /backend).
"""Business logic for logistics operations."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from .models import (
    LogisticsResourceRequest,
    LogisticsRequestApproval,
    LogisticsRequestAssignment,
    LogisticsResourceItem,
    ResourceRequestCreate,
    RequestApprovalCreate,
    RequestAssignmentCreate,
    EquipmentItem,
    CheckTransaction,
    EquipmentItemCreate,
)

from .repository import get_incident_engine, with_incident_session


# Resource request operations

def create_request(incident_id: str, data: ResourceRequestCreate) -> LogisticsResourceRequest:
    with with_incident_session(incident_id) as session:
        req = LogisticsResourceRequest(incident_id=incident_id, **data.dict())
        session.add(req)
        session.flush()
        return req


def approve_request(
    incident_id: str, request_id: int, data: RequestApprovalCreate
) -> LogisticsRequestApproval:
    with with_incident_session(incident_id) as session:
        approval = LogisticsRequestApproval(request_id=request_id, **data.dict())
        session.add(approval)
        req = session.get(LogisticsResourceRequest, request_id)
        if data.action == "Approve":
            req.status = "Approved"
        elif data.action == "Deny":
            req.status = "Denied"
        session.flush()
        return approval


def assign_request(
    incident_id: str, request_id: int, data: RequestAssignmentCreate
) -> LogisticsRequestAssignment:
    with with_incident_session(incident_id) as session:
        assignment = LogisticsRequestAssignment(
            request_id=request_id,
            assigned_datetime=datetime.utcnow(),
            **data.dict(),
        )
        session.add(assignment)
        req = session.get(LogisticsResourceRequest, request_id)
        req.status = "Assigned"
        session.flush()
        return assignment


def update_request_status(
    incident_id: str, request_id: int, status: str, actor_id: int
) -> LogisticsResourceRequest:
    with with_incident_session(incident_id) as session:
        req = session.get(LogisticsResourceRequest, request_id)
        req.status = status
        session.flush()
        return req


# Equipment operations

def add_equipment(incident_id: str, data: EquipmentItemCreate) -> EquipmentItem:
    with with_incident_session(incident_id) as session:
        item = EquipmentItem(**data.dict())
        session.add(item)
        session.flush()
        return item


def checkout_equipment(
    incident_id: str, equipment_id: int, actor_id: int, notes: Optional[str] = None
) -> EquipmentItem:
    with with_incident_session(incident_id) as session:
        item = session.get(EquipmentItem, equipment_id)
        item.status = "checked_out"
        item.current_holder_id = actor_id
        session.add(
            CheckTransaction(
                equipment_id=equipment_id,
                actor_id=actor_id,
                incident_id=incident_id,
                action="check_out",
                notes=notes,
            )
        )
        session.flush()
        session.refresh(item)
        return item


def checkin_equipment(
    incident_id: str, equipment_id: int, actor_id: int, notes: Optional[str] = None
) -> EquipmentItem:
    with with_incident_session(incident_id) as session:
        item = session.get(EquipmentItem, equipment_id)
        item.status = "available"
        item.current_holder_id = None
        session.add(
            CheckTransaction(
                equipment_id=equipment_id,
                actor_id=actor_id,
                incident_id=incident_id,
                action="check_in",
                notes=notes,
            )
        )
        session.flush()
        session.refresh(item)
        return item
