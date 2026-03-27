# AUTO-GENERATED: Logistics module for Incident Management Assistant
# NOTE: Module code lives under /modules/logistics (not /backend).
"""Incident database routing helpers for logistics."""

from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base

_engine_cache: Dict[str, Any] = {}


def get_incident_engine(incident_id: str):
    """Return an engine bound to the incident-specific database."""
    from utils import incident_storage
    paths = incident_storage.resolve_incident_paths_by_identifier(incident_id)
    if paths is None:
        meta = incident_storage.infer_incident_metadata(incident_id)
        paths = incident_storage.get_incident_paths(incident_number=meta.get("incident_number") or incident_id, incident_name=meta.get("name") or incident_id, incident_id=meta.get("incident_id") or incident_id)
        incident_storage.ensure_incident_structure(paths, meta)
    db_path = paths.incident_db
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = _engine_cache.get(incident_id)
    if engine is None:
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        _engine_cache[incident_id] = engine
    return engine


@contextmanager
def with_incident_session(incident_id: str):
    """Context manager yielding a session for the incident database."""
    engine = get_incident_engine(incident_id)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
