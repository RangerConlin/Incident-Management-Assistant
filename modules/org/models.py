"""SQLAlchemy models for incident organization structures and assignments."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    String,
    Integer,
    ForeignKey,
    JSON,
    CheckConstraint,
    Index,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modules._infra.base import Base


class OrgStructure(Base):
    __tablename__ = "org_structures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("org_structures.id", ondelete="CASCADE"), nullable=True
    )
    incident_id: Mapped[str] = mapped_column(String, index=True)
    op_id: Mapped[int] = mapped_column(Integer, index=True)
    node_type: Mapped[str] = mapped_column(String)
    role_code: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    flags_json: Mapped[dict | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent = relationship("OrgStructure", remote_side=[id], backref="children")


class OrgAssignment(Base):
    __tablename__ = "org_assignments"
    __table_args__ = (
        CheckConstraint(
            "assignment_role IN ('primary','deputy','assistant','trainee')",
            name="chk_assignment_role",
        ),
        Index(
            "ux_primary_per_node_per_op",
            "incident_id",
            "op_id",
            "node_id",
            unique=True,
            sqlite_where=text("assignment_role = 'primary'"),
        ),
        Index(
            "ux_deputy_per_node_per_op",
            "incident_id",
            "op_id",
            "node_id",
            unique=True,
            sqlite_where=text("assignment_role = 'deputy'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[str] = mapped_column(String, index=True)
    op_id: Mapped[int] = mapped_column(Integer, index=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("org_structures.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[str] = mapped_column(String)
    assignment_role: Mapped[str] = mapped_column(String, default="primary")
    start_ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    end_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    node = relationship("OrgStructure", backref="assignments")


class OrgVersion(Base):
    __tablename__ = "org_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[str] = mapped_column(String, index=True)
    op_id: Mapped[int] = mapped_column(Integer, index=True)
    label: Mapped[str] = mapped_column(String)
    snapshot_json: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OrgAudit(Base):
    __tablename__ = "org_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[str] = mapped_column(String, index=True)
    op_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    details_json: Mapped[dict | None] = mapped_column(JSON, default=dict)
    at_ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
