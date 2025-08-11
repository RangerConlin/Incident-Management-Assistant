import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models.safety_models import Base

DATA_DIR = Path("data/missions")


def get_mission_engine(mission_id: str):
    mission_path = DATA_DIR / f"{mission_id}.db"
    mission_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{mission_path}", future=True)
    Base.metadata.create_all(engine)
    return engine


@contextmanager
def with_mission_session(mission_id: str) -> Session:
    engine = get_mission_engine(mission_id)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
