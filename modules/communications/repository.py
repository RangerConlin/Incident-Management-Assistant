"""Database helpers for communications module."""

from pathlib import Path
from sqlmodel import SQLModel, create_engine

DATA_DIR = Path("data")
MASTER_DB = DATA_DIR / "master.db"
MISSIONS_DIR = DATA_DIR / "missions"


def get_engine(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}")


def get_master_engine():
    """Return engine for the master communications library."""
    engine = get_engine(MASTER_DB)
    SQLModel.metadata.create_all(engine)
    return engine


def get_mission_engine(mission_id: str):
    """Return engine for a mission-specific database."""
    path = MISSIONS_DIR / f"{mission_id}.db"
    engine = get_engine(path)
    SQLModel.metadata.create_all(engine)
    return engine
