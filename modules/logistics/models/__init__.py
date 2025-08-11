# AUTO-GENERATED: Logistics module for Incident Management Assistant
# NOTE: Module code lives under /modules/logistics (not /backend).

"""SQLAlchemy base and model exports for logistics."""

from sqlalchemy.orm import declarative_base

Base = declarative_base()

# convenient re-exports
from .resource_request import (
    LogisticsResourceRequest,
    LogisticsRequestApproval,
    LogisticsRequestAssignment,
    LogisticsResourceItem,
)

from .equipment import (
    EquipmentItem,
    CheckTransaction,
)

from .schemas import (
    ResourceRequestCreate,
    ResourceRequestRead,
    RequestApprovalCreate,
    RequestAssignmentCreate,
    EquipmentItemCreate,
    EquipmentItemRead,
    PermissionOut,
)

__all__ = [
    "Base",
    "LogisticsResourceRequest",
    "LogisticsRequestApproval",
    "LogisticsRequestAssignment",
    "LogisticsResourceItem",
    "ResourceRequestCreate",
    "ResourceRequestRead",
    "RequestApprovalCreate",
    "RequestAssignmentCreate",
    "EquipmentItem",
    "CheckTransaction",
    "EquipmentItemCreate",
    "EquipmentItemRead",
    "PermissionOut",
]
