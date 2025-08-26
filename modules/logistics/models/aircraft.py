from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from . import Base

class Aircraft(Base):
    __tablename__ = "aircraft"

    id = Column(Integer, primary_key=True)
    make = Column(String, nullable=False)
    model = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    tail_number = Column(String, unique=True, nullable=False)
    status = Column(String, default="available")
    location = Column(String)
    current_holder_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AircraftCheckTransaction(Base):
    __tablename__ = "aircraft_check_transactions"

    id = Column(Integer, primary_key=True)
    aircraft_id = Column(Integer, ForeignKey("aircraft.id"), nullable=False)
    actor_id = Column(Integer, nullable=False)
    mission_id = Column(String, nullable=False)
    action = Column(String, nullable=False)  # check_out or check_in
    timestamp = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)

