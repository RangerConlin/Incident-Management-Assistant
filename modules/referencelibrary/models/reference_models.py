"""SQLAlchemy models for the Reference Library."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, Session, sessionmaker

Base = declarative_base()


class Document(Base):
    __tablename__ = "library_documents"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    category = Column(String, nullable=False)
    subcategory = Column(String)
    tags = Column(Text)
    agency = Column(String)
    jurisdiction = Column(String)
    description = Column(Text)
    file_path = Column(String, nullable=False)
    file_hash = Column(String, nullable=False)
    file_ext = Column(String)
    file_size = Column(Integer)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)
    created_by = Column(String)
    modified_by = Column(String)
    archived = Column(Boolean, default=False)
    version = Column(String)


class Collection(Base):
    __tablename__ = "library_collections"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    created_by = Column(String)

    documents = relationship(
        "Document", secondary="collection_documents", backref="collections"
    )


class CollectionDocument(Base):
    __tablename__ = "collection_documents"

    collection_id = Column(Integer, ForeignKey("library_collections.id"), primary_key=True)
    document_id = Column(Integer, ForeignKey("library_documents.id"), primary_key=True)


# FTS table will be created via raw SQL


def get_engine():
    path = Path("data/master.db")
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", future=True)


@dataclass
class Metadata:
    size: int
    extension: str


def get_session(engine) -> Generator[Session, None, None]:
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()
