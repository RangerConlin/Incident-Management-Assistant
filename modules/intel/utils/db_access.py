"""Database helpers for the intel module.

The application uses a dual database strategy.  Functions in this module
provide SQLModel engines and sessions for both the persistent master
reference database and the per-incident operational database.  Tables are
created on demand when :func:`ensure_incident_schema` is called.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import os
from typing import Iterator

from sqlmodel import SQLModel, create_engine, Session

from utils import incident_context

DATA_DIR = Path(os.environ.get("CHECKIN_DATA_DIR", "data"))
MASTER_DB_PATH = DATA_DIR / "master.db"


def _engine(path: Path):
    return create_engine(f"sqlite:///{path}")


def get_master_engine():
    """Return SQLModel engine for the master database."""
    return _engine(MASTER_DB_PATH)


def get_incident_engine():
    """Return SQLModel engine for the active incident database."""
    path = incident_context.get_active_incident_db_path()
    return _engine(path)


@contextmanager
def incident_session() -> Iterator[Session]:
    """Context manager yielding a session for the active incident database."""
    engine = get_incident_engine()
    with Session(engine) as session:
        yield session


def ensure_incident_schema() -> None:
    """Create intel tables in the active incident database if missing."""
    engine = get_incident_engine()
    SQLModel.metadata.create_all(engine)
