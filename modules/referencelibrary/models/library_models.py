"""SQLAlchemy models for the reference library."""

from __future__ import annotations

import datetime as dt
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    size_bytes = Column(Integer, default=0)
    checksum = Column(String)
    tags_json = Column(Text)
    agency = Column(String)
    category = Column(String)
    access_level = Column(String)
    uploader_id = Column(String)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(
        DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )
    is_offline_cached = Column(Integer, default=0)
    extracted_text = Column(Text)


class Collection(Base):
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    created_by = Column(String)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    documents = relationship(
        "Document", secondary="collection_documents", backref="collections"
    )


class CollectionDocument(Base):
    __tablename__ = "collection_documents"

    collection_id = Column(
        Integer, ForeignKey("collections.id"), primary_key=True
    )
    document_id = Column(Integer, ForeignKey("documents.id"), primary_key=True)


class ExternalLink(Base):
    __tablename__ = "external_links"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    description = Column(Text)
    tags_json = Column(Text)
    added_by = Column(String)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class IncidentDocument(Base):
    __tablename__ = "incident_documents"

    id = Column(Integer, primary_key=True)
    incident_id = Column(String, nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    note = Column(Text)
    added_by = Column(String)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class AuditEntry(Base):
    __tablename__ = "library_audit"

    id = Column(Integer, primary_key=True)
    event = Column(Text, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
