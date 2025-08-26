import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models.safety_models import Base

DATA_DIR = Path("data/incidents")


def get_incident_engine(incident_id: str):
    incident_path = DATA_DIR / f"{incident_id}.db"
    incident_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{incident_path}", future=True)
    Base.metadata.create_all(engine)
    return engine


@contextmanager
def with_incident_session(incident_id: str) -> Session:
    engine = get_incident_engine(incident_id)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
