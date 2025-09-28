"""Incident database routing helpers for ICS-214 and other modules."""

from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from modules._infra.base import Base
# Import model modules so tables are registered on Base metadata
import modules.ics214.models  # noqa: F401
import modules.org.models  # noqa: F401
import modules.command.models.objectives  # noqa: F401

_engine_cache: Dict[str, Any] = {}


def get_incident_engine(incident_id: str):
    """Return an engine bound to incident-specific database."""
    db_path = Path("data") / "incidents" / f"{incident_id}.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = _engine_cache.get(incident_id)
    if engine is None:
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        _engine_cache[incident_id] = engine
    return engine


@contextmanager
def with_incident_session(incident_id: str):
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
