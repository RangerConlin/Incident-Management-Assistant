from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from . import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True)
    make = Column(String, nullable=False)
    model = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    vin = Column(String, unique=True, nullable=False)
    status = Column(String, default="available")
    location = Column(String)
    current_holder_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VehicleCheckTransaction(Base):
    __tablename__ = "vehicle_check_transactions"

    id = Column(Integer, primary_key=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    actor_id = Column(Integer, nullable=False)
    mission_id = Column(String, nullable=False)
    action = Column(String, nullable=False)  # check_out or check_in
    timestamp = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)

class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"

    id = Column(Integer, primary_key=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    maintenance_type = Column(String, nullable=False)
    description = Column(Text)
    performed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

class VehicleInspectionRecord(Base):
    __tablename__ = "vehicle_inspection_records"

    id = Column(Integer, primary_key=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    inspected_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    inspection_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String, nullable=False)
    notes = Column(Text)
