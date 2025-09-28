"""Incident database routing helpers for ICS-214 and other modules."""

from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any

from sqlalchemy import create_engine
import sqlite3
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
        # Defensive: make sure legacy DBs have modern columns expected by
        # Command module ORM for `incident_objectives`.
        try:
            _ensure_objectives_columns(db_path)
        except Exception:
            # Do not block engine creation if the passive migration fails.
            pass
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


def _ensure_objectives_columns(db_path: Path) -> None:
    """Add missing columns to `incident_objectives` if the table exists.

    This is a lightweight, non-destructive migration for older databases that
    were created by the QML bridge with a reduced schema. It ensures the ORM
    can safely SELECT the full column set without OperationalError.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        # If table doesn't exist, nothing to do — SQLAlchemy already created it
        tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "incident_objectives" not in tables:
            return
        existing_cols = {r[1] for r in cur.execute("PRAGMA table_info(incident_objectives)")}
        required = [
            ("incident_id", "TEXT"),
            ("op_period_id", "INTEGER"),
            ("code", "TEXT"),
            ("text", "TEXT"),
            ("owner_section", "TEXT"),
            ("tags_json", "TEXT"),
            ("display_order", "INTEGER DEFAULT 0"),
            ("updated_at", "TEXT"),
            ("updated_by", "TEXT"),
        ]
        for col, decl in required:
            if col not in existing_cols:
                try:
                    cur.execute(f"ALTER TABLE incident_objectives ADD COLUMN {col} {decl}")
                except sqlite3.OperationalError:
                    pass
        conn.commit()
    finally:
        conn.close()
