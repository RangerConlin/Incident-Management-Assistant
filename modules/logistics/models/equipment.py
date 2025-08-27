"""Equipment inventory and check transaction SQLAlchemy models."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from . import Base


class EquipmentItem(Base):
    __tablename__ = "equipment_items"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    type_id = Column(String)
    serial_number = Column(String)
    status = Column(String, default="available")
    location = Column(String)
    current_holder_id = Column(Integer)
    tags = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CheckTransaction(Base):
    __tablename__ = "check_transactions"

    id = Column(Integer, primary_key=True)
    equipment_id = Column(Integer, ForeignKey("equipment_items.id"), nullable=False)
    actor_id = Column(Integer, nullable=False)
    incident_id = Column(String, nullable=False)
    action = Column(String, nullable=False)  # check_out or check_in
    timestamp = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)
