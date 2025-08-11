"""Database connection helpers for the reference library module."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models.library_models import Base

ROOT_DIR = Path(__file__).resolve().parents[2]


def _build_engine(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    return engine


def get_master_engine() -> Engine:
    """Return an engine bound to the master library database."""
    engine = _build_engine(ROOT_DIR / "data" / "master.db")
    ensure_tables(engine)
    return engine


def get_mission_engine(mission_id: str) -> Engine:
    """Return an engine bound to a mission-specific database."""
    engine = _build_engine(ROOT_DIR / "data" / "missions" / f"{mission_id}.db")
    ensure_tables(engine)
    return engine


def ensure_tables(engine: Engine) -> None:
    """Create all tables and FTS indices if they do not exist."""
    Base.metadata.create_all(engine)
    from .search_index import ensure_fts

    ensure_fts(engine)


@contextmanager
def with_master_session() -> Generator[Session, None, None]:
    """Yield a session for the master database."""
    engine = get_master_engine()
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()


@contextmanager
def with_mission_session(mission_id: str) -> Generator[Session, None, None]:
    """Yield a session for a mission database."""
    engine = get_mission_engine(mission_id)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()
