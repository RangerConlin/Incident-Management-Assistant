# AUTO-GENERATED: Logistics module for Incident Management Assistant
# NOTE: Module code lives under /modules/logistics (not /backend).

"""Resource request related SQLAlchemy models."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from . import Base


class LogisticsResourceRequest(Base):
    __tablename__ = "logistics_resource_requests"

    id = Column(Integer, primary_key=True)
    mission_id = Column(String, nullable=False)
    requestor_id = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    item_code = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    priority = Column(String, nullable=False)
    justification = Column(Text)
    status = Column(String, default="Submitted")
    due_datetime = Column(DateTime)
    notes = Column(Text)


class LogisticsRequestApproval(Base):
    __tablename__ = "logistics_request_approvals"

    id = Column(Integer, primary_key=True)
    request_id = Column(
        Integer, ForeignKey("logistics_resource_requests.id"), nullable=False
    )
    approver_id = Column(Integer, nullable=False)
    action = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    comments = Column(Text)


class LogisticsRequestAssignment(Base):
    __tablename__ = "logistics_request_assignments"

    id = Column(Integer, primary_key=True)
    request_id = Column(
        Integer, ForeignKey("logistics_resource_requests.id"), nullable=False
    )
    resource_id = Column(Integer)
    assigned_to_id = Column(Integer)
    assigned_datetime = Column(DateTime)
    eta = Column(DateTime)
    status = Column(String, default="pending")


class LogisticsResourceItem(Base):
    __tablename__ = "logistics_resource_items"

    item_code = Column(String, primary_key=True)
    description = Column(String, nullable=False)
    unit = Column(String, nullable=False)
    available_quantity = Column(Integer, default=0)
    location = Column(String)

