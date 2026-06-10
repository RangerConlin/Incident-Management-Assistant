from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from utils import incident_storage
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .planned_models import MasterBase, EventBase

DATA_ROOT = incident_storage.data_root()
MASTER_DB = incident_storage.master_db_path()
INCIDENTS_DIR = incident_storage.incidents_root()


def get_master_engine():
    MASTER_DB.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{MASTER_DB}", future=True)
    MasterBase.metadata.create_all(engine)
    return engine


def get_event_engine(event_id: str):
    paths = incident_storage.resolve_incident_paths_by_identifier(event_id)
    if paths is None:
        meta = incident_storage.infer_incident_metadata(event_id)
        paths = incident_storage.get_incident_paths(incident_number=meta.get("incident_number") or event_id, incident_name=meta.get("name") or event_id, incident_id=meta.get("incident_id") or event_id)
        incident_storage.ensure_incident_structure(paths, meta)
    db_path = paths.incident_db
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
