# AUTO-GENERATED: Logistics module for Incident Management Assistant
# NOTE: Module code lives under /modules/logistics (not /backend).
"""Mission database routing helpers for logistics."""

from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base

_engine_cache: Dict[str, Any] = {}


def get_mission_engine(mission_id: str):
    """Return an engine bound to the mission-specific database."""
    db_path = Path("data") / "missions" / f"{mission_id}.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = _engine_cache.get(mission_id)
    if engine is None:
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        _engine_cache[mission_id] = engine
    return engine


@contextmanager
def with_mission_session(mission_id: str):
    """Context manager yielding a session for the mission database."""
    engine = get_mission_engine(mission_id)
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
