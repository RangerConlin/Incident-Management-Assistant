import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models.safety_models import Base

from utils import incident_storage

DATA_DIR = incident_storage.incidents_root()


def get_incident_engine(incident_id: str):
    paths = incident_storage.resolve_incident_paths_by_identifier(incident_id)
    if paths is None:
        meta = incident_storage.infer_incident_metadata(incident_id)
        paths = incident_storage.get_incident_paths(incident_number=meta.get("incident_number") or incident_id, incident_name=meta.get("name") or incident_id, incident_id=meta.get("incident_id") or incident_id)
        incident_storage.ensure_incident_structure(paths, meta)
    incident_path = paths.incident_db
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
