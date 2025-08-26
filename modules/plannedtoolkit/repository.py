from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .planned_models import MasterBase, EventBase

DATA_ROOT = Path("data")
MASTER_DB = DATA_ROOT / "master.db"
INCIDENTS_DIR = DATA_ROOT / "incidents"


def get_master_engine():
    MASTER_DB.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{MASTER_DB}", future=True)
    MasterBase.metadata.create_all(engine)
    return engine


def get_event_engine(event_id: str):
    db_path = INCIDENTS_DIR / f"{event_id}.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    EventBase.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("CREATE VIRTUAL TABLE IF NOT EXISTS attachment_fts USING fts5(title, content)") )
    return engine


@contextmanager
def with_master_session():
    engine = get_master_engine()
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()


@contextmanager
def with_event_session(event_id: str):
    engine = get_event_engine(event_id)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()
