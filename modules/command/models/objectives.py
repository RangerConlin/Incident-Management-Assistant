from __future__ import annotations

"""Incident Objectives data access layer for the Command module."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Optional, Sequence

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from modules._infra.base import Base

try:  # pragma: no cover - optional dependency in some runtimes
    from modules.operations.taskings.models import Task  # type: ignore
    from modules.operations.taskings.repository import get_task  # type: ignore
except Exception:  # pragma: no cover - operations module not always available
    Task = None  # type: ignore[assignment]

    def get_task(task_id: int) -> Task:  # type: ignore[override]
        raise RuntimeError("Taskings repository is not available in this environment")


PRIORITY_VALUES = ["low", "normal", "high", "urgent"]
STATUS_VALUES = ["draft", "active", "deferred", "completed", "cancelled"]
STRATEGY_STATUS_VALUES = ["planned", "in_progress", "blocked", "done"]

_OPEN_TASK_STATUSES = {"created", "draft", "planned", "assigned", "in progress"}


class IncidentObjective(Base):
    """SQLAlchemy ORM model for high-level incident objectives."""

    __tablename__ = "incident_objectives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Many legacy databases include a NOT NULL mission_id used by QML code paths.
    # Include it here with a safe default to satisfy NOT NULL constraints.
    mission_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    incident_id: Mapped[str] = mapped_column(String, index=True)
    op_period_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    code: Mapped[str] = mapped_column(String, index=True)
    text: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String, default="normal")
    status: Mapped[str] = mapped_column(String, default="draft")
    owner_section: Mapped[str | None] = mapped_column(String, nullable=True)
    tags_json: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String, nullable=True)

    strategies = relationship(
        "ObjectiveStrategy",
        back_populates="objective",
        cascade="all, delete-orphan",
        order_by="ObjectiveStrategy.id",
    )
    task_links = relationship(
        "ObjectiveStrategyTaskLink",
        back_populates="objective",
        cascade="all, delete-orphan",
    )
    audit_logs = relationship(
        "ObjectiveAuditLog",
        back_populates="objective",
        cascade="all, delete-orphan",
        order_by="ObjectiveAuditLog.ts.desc()",
    )


class ObjectiveStrategy(Base):
    """Implementation strategy supporting an incident objective."""

    __tablename__ = "objective_strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    objective_id: Mapped[int] = mapped_column(
        ForeignKey("incident_objectives.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    owner: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="planned")
    progress_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    objective = relationship("IncidentObjective", back_populates="strategies")
    task_links = relationship(
        "ObjectiveStrategyTaskLink",
        back_populates="strategy",
        cascade="all, delete-orphan",
    )


class ObjectiveStrategyTaskLink(Base):
    """Associates an Operations task with an objective strategy."""

    __tablename__ = "objective_strategy_task_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    objective_id: Mapped[int] = mapped_column(
        ForeignKey("incident_objectives.id", ondelete="CASCADE"), index=True
    )
    strategy_id: Mapped[int] = mapped_column(
        ForeignKey("objective_strategies.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    objective = relationship("IncidentObjective", back_populates="task_links")
    strategy = relationship("ObjectiveStrategy", back_populates="task_links")


class ObjectiveAuditLog(Base):
    """Simple audit log capturing mutations to objectives and strategies."""

    __tablename__ = "objective_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    objective_id: Mapped[int] = mapped_column(
        ForeignKey("incident_objectives.id", ondelete="CASCADE"), index=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    field: Mapped[str] = mapped_column(String)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)

    objective = relationship("IncidentObjective", back_populates="audit_logs")


@dataclass(slots=True)
class ObjectiveStrategyView:
    """Serializable view model for a strategy row."""

    id: int
    objective_id: int
    text: str
    owner: str | None
    status: str
    progress_pct: int | None
    open_tasks: int = 0
    total_tasks: int = 0


@dataclass(slots=True)
class ObjectiveTaskInfo:
    """Task roll-up row for the Tasks tab."""

    link_id: int
    task_db_id: int
    strategy_id: int
    strategy_text: str
    task_number: str
    title: str
    status: str
    due: str | None
    assignee: str | None
    is_open: bool


@dataclass(slots=True)
class TaskObjectiveLink:
    """Represents a linkage between a task and an objective/strategy."""

    link_id: int
    objective_id: int
    objective_code: str
    objective_text: str
    strategy_id: int
    strategy_text: str


@dataclass(slots=True)
class ObjectiveSummary:
    """Summary row exposed to the table model."""

    id: int
    code: str
    text: str
    priority: str
    status: str
    owner_section: str | None
    tags: list[str]
    op_period_id: int | None
    updated_at: datetime | None
    updated_by: str | None
    display_order: int
    strategies: int = 0
    open_tasks: int = 0
    total_tasks: int = 0


@dataclass(slots=True)
class ObjectiveDetail:
    """Complete objective detail for the dialog."""

    summary: ObjectiveSummary
    strategies: list[ObjectiveStrategyView] = field(default_factory=list)
    tasks: list[ObjectiveTaskInfo] = field(default_factory=list)
    narrative: str | None = None


@dataclass(slots=True)
class ObjectiveFilters:
    """Filter parameters for list queries."""

    status: Optional[Sequence[str]] = None
    priority: Optional[Sequence[str]] = None
    op_period_id: Optional[int] = None
    search: Optional[str] = None
    has_strategies: Optional[bool] = None
    has_open_tasks: Optional[bool] = None


class ObjectiveRepository:
    """Repository encapsulating Objective persistence logic."""

    def __init__(self, session: Session, incident_id: str):
        self.session = session
        self.incident_id = str(incident_id)

    # ------------------------------------------------------------------
    # Objective CRUD
    # ------------------------------------------------------------------
    def list_objectives(self, filters: ObjectiveFilters | None = None) -> list[ObjectiveSummary]:
        filters = filters or ObjectiveFilters()
        stmt = (
            select(IncidentObjective)
            .where(IncidentObjective.incident_id == self.incident_id)
            .order_by(IncidentObjective.display_order.asc(), IncidentObjective.id.asc())
        )
        if filters.status:
            stmt = stmt.where(IncidentObjective.status.in_(list(filters.status)))
        if filters.priority:
            stmt = stmt.where(IncidentObjective.priority.in_(list(filters.priority)))
        if filters.op_period_id is not None:
            stmt = stmt.where(IncidentObjective.op_period_id == filters.op_period_id)
        if filters.search:
            token = f"%{filters.search.lower()}%"
            stmt = stmt.where(func.lower(IncidentObjective.text).like(token))

        rows = self.session.execute(stmt).scalars().all()
        objective_ids = [row.id for row in rows]
        strategy_counts: dict[int, int] = {}
        if objective_ids:
            result = self.session.execute(
                select(
                    ObjectiveStrategy.objective_id, func.count(ObjectiveStrategy.id)
                ).where(ObjectiveStrategy.objective_id.in_(objective_ids))
                .group_by(ObjectiveStrategy.objective_id)
            )
            strategy_counts = {oid: count for oid, count in result}

        task_totals: dict[int, int] = {}
        if objective_ids:
            result = self.session.execute(
                select(
                    ObjectiveStrategyTaskLink.objective_id,
                    func.count(ObjectiveStrategyTaskLink.id),
                )
                .where(ObjectiveStrategyTaskLink.objective_id.in_(objective_ids))
                .group_by(ObjectiveStrategyTaskLink.objective_id)
            )
            task_totals = {oid: total for oid, total in result}

        summaries: list[ObjectiveSummary] = []
        for obj in rows:
            open_tasks = self._count_open_tasks(obj.id)
            summary = ObjectiveSummary(
                id=obj.id,
                code=obj.code,
                text=obj.text,
                priority=obj.priority,
                status=obj.status,
                owner_section=obj.owner_section,
                tags=list(obj.tags_json or []),
                op_period_id=obj.op_period_id,
                updated_at=obj.updated_at,
                updated_by=obj.updated_by,
                display_order=obj.display_order,
                strategies=strategy_counts.get(obj.id, 0),
                open_tasks=open_tasks,
                total_tasks=task_totals.get(obj.id, 0),
            )
            if filters.has_open_tasks is None or bool(summary.open_tasks) == filters.has_open_tasks:
                summaries.append(summary)
        return summaries

    def create_objective(self, payload: dict, user_id: str | None = None) -> ObjectiveDetail:
        code = payload.get("code") or self._generate_objective_code()
        display_order = payload.get("display_order")
        if display_order is None:
            display_order = self._next_display_order()
        objective = IncidentObjective(
            incident_id=self.incident_id,
            op_period_id=payload.get("op_period_id"),
            code=code,
            text=payload.get("text", "").strip(),
            priority=self._validate_priority(payload.get("priority", "normal")),
            status=self._validate_status(payload.get("status", "draft")),
            owner_section=payload.get("owner_section"),
            tags_json=list(payload.get("tags", [])),
            display_order=int(display_order),
            created_by=user_id,
            updated_by=user_id,
        )
        self.session.add(objective)
        self.session.flush()
        self._record_audit(objective.id, "objective.create", None, objective.text, user_id)
        return self.get_objective_detail(objective.id)

    def update_objective(self, objective_id: int, payload: dict, user_id: str | None = None) -> ObjectiveDetail:
        objective = self.session.get(IncidentObjective, objective_id)
        if not objective or objective.incident_id != self.incident_id:
            raise ValueError(f"Objective {objective_id} not found for incident {self.incident_id}")

        changed_fields: list[tuple[str, str | None, str | None]] = []
        if "text" in payload:
            new_text = str(payload["text"]).strip()
            if new_text != objective.text:
                changed_fields.append(("text", objective.text, new_text))
                objective.text = new_text
        if "priority" in payload:
            new_priority = self._validate_priority(payload["priority"])
            if new_priority != objective.priority:
                changed_fields.append(("priority", objective.priority, new_priority))
                objective.priority = new_priority
        if "status" in payload:
            new_status = self._validate_status(payload["status"])
            if new_status != objective.status:
                changed_fields.append(("status", objective.status, new_status))
                objective.status = new_status
        if "owner_section" in payload:
            new_owner = payload.get("owner_section")
            if new_owner != objective.owner_section:
                changed_fields.append(("owner_section", objective.owner_section, new_owner))
                objective.owner_section = new_owner
        if "tags" in payload:
            new_tags = list(payload.get("tags") or [])
            if new_tags != list(objective.tags_json or []):
                changed_fields.append(("tags", str(objective.tags_json or []), str(new_tags)))
                objective.tags_json = new_tags
        if "op_period_id" in payload:
            new_op = payload.get("op_period_id")
            if new_op != objective.op_period_id:
                changed_fields.append(("op_period_id", str(objective.op_period_id), str(new_op)))
                objective.op_period_id = new_op

        objective.updated_by = user_id
        objective.updated_at = datetime.utcnow()
        self.session.flush()

        for field, old, new in changed_fields:
            self._record_audit(objective.id, f"objective.{field}", old, new, user_id)

        return self.get_objective_detail(objective.id)

    def set_status(self, objective_id: int, status: str, user_id: str | None = None) -> ObjectiveDetail:
        return self.update_objective(objective_id, {"status": status}, user_id=user_id)

    def reorder_objectives(self, ordered_ids: Sequence[int], user_id: str | None = None) -> None:
        timestamp = datetime.utcnow()
        for position, obj_id in enumerate(ordered_ids):
            updated = self.session.execute(
                select(IncidentObjective).where(
                    IncidentObjective.id == obj_id,
                    IncidentObjective.incident_id == self.incident_id,
                )
            ).scalars().first()
            if not updated:
                continue
            if updated.display_order != position:
                self._record_audit(
                    updated.id,
                    "objective.reorder",
                    str(updated.display_order),
                    str(position),
                    user_id,
                )
                updated.display_order = position
                updated.updated_at = timestamp
                updated.updated_by = user_id
        self.session.flush()

    # ------------------------------------------------------------------
    # Strategies
    # ------------------------------------------------------------------
    def list_strategies(self, objective_id: int) -> list[ObjectiveStrategyView]:
        rows = (
            self.session.execute(
                select(ObjectiveStrategy).where(
                    ObjectiveStrategy.objective_id == objective_id
                ).order_by(ObjectiveStrategy.id.asc())
            )
            .scalars()
            .all()
        )
        rollup = self._strategy_task_rollup([row.id for row in rows])
        return [
            ObjectiveStrategyView(
                id=row.id,
                objective_id=row.objective_id,
                text=row.text,
                owner=row.owner,
                status=row.status,
                progress_pct=row.progress_pct,
                open_tasks=rollup.get(row.id, (0, 0))[0],
                total_tasks=rollup.get(row.id, (0, 0))[1],
            )
            for row in rows
        ]

    def add_strategy(
        self,
        objective_id: int,
        payload: dict,
        user_id: str | None = None,
    ) -> ObjectiveStrategyView:
        objective = self.session.get(IncidentObjective, objective_id)
        if not objective or objective.incident_id != self.incident_id:
            raise ValueError("Objective not found")
        strategy = ObjectiveStrategy(
            objective_id=objective_id,
            text=str(payload.get("text", "")).strip(),
            owner=payload.get("owner"),
            status=self._validate_strategy_status(payload.get("status", "planned")),
            progress_pct=payload.get("progress_pct"),
            created_by=user_id,
            updated_by=user_id,
        )
        self.session.add(strategy)
        self.session.flush()
        self._record_audit(
            objective_id,
            "strategy.create",
            None,
            strategy.text,
            user_id,
        )
        return ObjectiveStrategyView(
            id=strategy.id,
            objective_id=objective_id,
            text=strategy.text,
            owner=strategy.owner,
            status=strategy.status,
            progress_pct=strategy.progress_pct,
        )

    def update_strategy(
        self,
        objective_id: int,
        strategy_id: int,
        payload: dict,
        user_id: str | None = None,
    ) -> ObjectiveStrategyView:
        strategy = self.session.get(ObjectiveStrategy, strategy_id)
        if not strategy or strategy.objective_id != objective_id:
            raise ValueError("Strategy not found")

        changes: list[tuple[str, str | None, str | None]] = []
        if "text" in payload:
            new_text = str(payload["text"]).strip()
            if new_text != strategy.text:
                changes.append(("text", strategy.text, new_text))
                strategy.text = new_text
        if "owner" in payload:
            new_owner = payload.get("owner")
            if new_owner != strategy.owner:
                changes.append(("owner", strategy.owner, new_owner))
                strategy.owner = new_owner
        if "status" in payload:
            new_status = self._validate_strategy_status(payload["status"])
            if new_status != strategy.status:
                changes.append(("status", strategy.status, new_status))
                strategy.status = new_status
        if "progress_pct" in payload:
            new_progress = payload.get("progress_pct")
            if new_progress != strategy.progress_pct:
                changes.append(("progress_pct", str(strategy.progress_pct), str(new_progress)))
                strategy.progress_pct = new_progress

        strategy.updated_at = datetime.utcnow()
        strategy.updated_by = user_id
        self.session.flush()

        for field, old, new in changes:
            self._record_audit(strategy.objective_id, f"strategy.{field}", old, new, user_id)

        rollup = self._strategy_task_rollup([strategy.id]).get(strategy.id, (0, 0))
        return ObjectiveStrategyView(
            id=strategy.id,
            objective_id=strategy.objective_id,
            text=strategy.text,
            owner=strategy.owner,
            status=strategy.status,
            progress_pct=strategy.progress_pct,
            open_tasks=rollup[0],
            total_tasks=rollup[1],
        )

    def delete_strategy(self, objective_id: int, strategy_id: int, user_id: str | None = None) -> None:
        strategy = self.session.get(ObjectiveStrategy, strategy_id)
        if not strategy or strategy.objective_id != objective_id:
            return
        self._record_audit(
            objective_id,
            "strategy.delete",
            strategy.text,
            None,
            user_id,
        )
        self.session.delete(strategy)
        self.session.flush()

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------
    def link_task(
        self,
        objective_id: int,
        strategy_id: int,
        task_id: int,
        user_id: str | None = None,
    ) -> ObjectiveTaskInfo:
        objective = self.session.get(IncidentObjective, objective_id)
        if not objective or objective.incident_id != self.incident_id:
            raise ValueError("Objective not found")
        strategy = self.session.get(ObjectiveStrategy, strategy_id)
        if not strategy or strategy.objective_id != objective_id:
            raise ValueError("Strategy not found")

        link = ObjectiveStrategyTaskLink(
            objective_id=objective_id,
            strategy_id=strategy_id,
            task_id=int(task_id),
        )
        self.session.add(link)
        self.session.flush()
        self._record_audit(
            objective_id,
            "task.link",
            None,
            f"task_id={task_id}",
            user_id,
        )
        return self._build_task_info(link, strategy)

    def unlink_task(self, link_id: int, user_id: str | None = None) -> None:
        link = self.session.get(ObjectiveStrategyTaskLink, link_id)
        if not link:
            return
        strategy = self.session.get(ObjectiveStrategy, link.strategy_id)
        self._record_audit(
            link.objective_id,
            "task.unlink",
            f"task_id={link.task_id}",
            None,
            user_id,
        )
        self.session.delete(link)
        self.session.flush()
        if strategy:
            strategy.updated_at = datetime.utcnow()
            strategy.updated_by = user_id
        self.session.flush()

    def list_links_for_task(self, task_id: int) -> list[TaskObjectiveLink]:
        """Return existing objective/strategy links for the given task id."""
        rows = (
            self.session.execute(
                select(
                    ObjectiveStrategyTaskLink.id,
                    IncidentObjective.id,
                    IncidentObjective.code,
                    IncidentObjective.text,
                    ObjectiveStrategy.id,
                    ObjectiveStrategy.text,
                )
                .where(
                    ObjectiveStrategyTaskLink.task_id == int(task_id),
                    ObjectiveStrategyTaskLink.objective_id == IncidentObjective.id,
                    ObjectiveStrategyTaskLink.strategy_id == ObjectiveStrategy.id,
                )
                .order_by(IncidentObjective.display_order.asc(), ObjectiveStrategy.id.asc())
            )
            .all()
        )
        out: list[TaskObjectiveLink] = []
        for link_id, obj_id, obj_code, obj_text, strat_id, strat_text in rows:
            out.append(
                TaskObjectiveLink(
                    link_id=int(link_id),
                    objective_id=int(obj_id),
                    objective_code=str(obj_code or ""),
                    objective_text=str(obj_text or ""),
                    strategy_id=int(strat_id),
                    strategy_text=str(strat_text or ""),
                )
            )
        return out

    def list_tasks(self, objective_id: int) -> list[ObjectiveTaskInfo]:
        strategies = {
            s.id: s
            for s in self.session.execute(
                select(ObjectiveStrategy).where(ObjectiveStrategy.objective_id == objective_id)
            )
            .scalars()
            .all()
        }
        links = (
            self.session.execute(
                select(ObjectiveStrategyTaskLink).where(
                    ObjectiveStrategyTaskLink.objective_id == objective_id
                )
            )
            .scalars()
            .all()
        )
        return [
            self._build_task_info(link, strategies.get(link.strategy_id))
            for link in links
        ]

    # ------------------------------------------------------------------
    # Detail / Export
    # ------------------------------------------------------------------
    def get_objective_detail(self, objective_id: int) -> ObjectiveDetail:
        objective = self.session.get(IncidentObjective, objective_id)
        if not objective or objective.incident_id != self.incident_id:
            raise ValueError("Objective not found")
        summary = ObjectiveSummary(
            id=objective.id,
            code=objective.code,
            text=objective.text,
            priority=objective.priority,
            status=objective.status,
            owner_section=objective.owner_section,
            tags=list(objective.tags_json or []),
            op_period_id=objective.op_period_id,
            updated_at=objective.updated_at,
            updated_by=objective.updated_by,
            display_order=objective.display_order,
        )
        strategies = self.list_strategies(objective_id)
        tasks = self.list_tasks(objective_id)
        summary.strategies = len(strategies)
        summary.total_tasks = len(tasks)
        summary.open_tasks = sum(1 for t in tasks if t.is_open)
        return ObjectiveDetail(summary=summary, strategies=strategies, tasks=tasks)

    def export_ics202(
        self,
        include_progress: bool = True,
        include_task_counts: bool = True,
        include_narrative: bool = False,
    ) -> dict:
        objectives = []
        for detail in self.list_objectives():
            obj_detail = self.get_objective_detail(detail.id)
            obj_payload = {
                "order": detail.display_order,
                "code": detail.code,
                "text": detail.text,
                "priority": detail.priority,
                "status": detail.status,
                "strategies": [],
            }
            for strategy in obj_detail.strategies:
                strat_payload = {
                    "id": strategy.id,
                    "text": strategy.text,
                    "status": strategy.status,
                }
                if include_progress:
                    strat_payload["progress_pct"] = strategy.progress_pct
                if include_task_counts:
                    strat_payload["open_tasks"] = strategy.open_tasks
                    strat_payload["total_tasks"] = strategy.total_tasks
                obj_payload["strategies"].append(strat_payload)
            if include_narrative:
                obj_payload["narrative"] = obj_detail.narrative or ""
            objectives.append(obj_payload)
        return {"operational_period": {}, "objectives": objectives}

    def list_history(self, objective_id: int) -> list[ObjectiveAuditLog]:
        return (
            self.session.execute(
                select(ObjectiveAuditLog)
                .where(ObjectiveAuditLog.objective_id == objective_id)
                .order_by(ObjectiveAuditLog.ts.desc())
            )
            .scalars()
            .all()
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _generate_objective_code(self) -> str:
        stmt = select(func.max(IncidentObjective.id)).where(
            IncidentObjective.incident_id == self.incident_id
        )
        last_id = self.session.execute(stmt).scalar()
        next_num = int(last_id or 0) + 1
        return f"OBJ-{next_num}"

    def _next_display_order(self) -> int:
        stmt = select(func.max(IncidentObjective.display_order)).where(
            IncidentObjective.incident_id == self.incident_id
        )
        current_max = self.session.execute(stmt).scalar()
        return int(current_max or 0) + 1

    def _validate_priority(self, value: str) -> str:
        value = (value or "normal").strip().lower()
        if value not in PRIORITY_VALUES:
            raise ValueError(f"Unsupported priority: {value}")
        return value

    def _validate_status(self, value: str) -> str:
        value = (value or "draft").strip().lower()
        if value not in STATUS_VALUES:
            raise ValueError(f"Unsupported status: {value}")
        return value

    def _validate_strategy_status(self, value: str) -> str:
        value = (value or "planned").strip().lower()
        if value not in STRATEGY_STATUS_VALUES:
            raise ValueError(f"Unsupported strategy status: {value}")
        return value

    def _record_audit(
        self,
        objective_id: int,
        field: str,
        old: str | None,
        new: str | None,
        user_id: str | None,
    ) -> None:
        entry = ObjectiveAuditLog(
            objective_id=objective_id,
            field=field,
            old_value=old,
            new_value=new,
            user_id=user_id,
        )
        self.session.add(entry)

    def _count_open_tasks(self, objective_id: int) -> int:
        tasks = self.list_tasks(objective_id)
        return sum(1 for task in tasks if task.is_open)

    def _strategy_task_rollup(self, strategy_ids: Iterable[int]) -> dict[int, tuple[int, int]]:
        strategy_ids = list(strategy_ids)
        if not strategy_ids:
            return {}
        rows = (
            self.session.execute(
                select(
                    ObjectiveStrategyTaskLink.strategy_id,
                    ObjectiveStrategyTaskLink.id,
                    ObjectiveStrategyTaskLink.task_id,
                ).where(ObjectiveStrategyTaskLink.strategy_id.in_(strategy_ids))
            )
            .all()
        )
        rollup: dict[int, tuple[int, int]] = {}
        for strategy_id in strategy_ids:
            rollup[strategy_id] = (0, 0)
        for strategy_id, link_id, task_id in rows:
            total_open, total = rollup.get(strategy_id, (0, 0))
            task_status = self._resolve_task_status(task_id)
            if task_status in _OPEN_TASK_STATUSES:
                total_open += 1
            total += 1
            rollup[strategy_id] = (total_open, total)
        return rollup

    def _resolve_task_status(self, task_id: int) -> str:
        try:
            task = get_task(int(task_id))
        except Exception:
            return ""
        status = getattr(task, "status", "")
        return str(status or "").strip().lower()

    def _build_task_info(
        self,
        link: ObjectiveStrategyTaskLink,
        strategy: ObjectiveStrategy | None,
    ) -> ObjectiveTaskInfo:
        try:
            task_obj = get_task(int(link.task_id))
        except Exception:
            task_obj = None
        task_number = ""
        title = ""
        status = ""
        due = None
        assignee = None
        if task_obj is not None:
            task_number = getattr(task_obj, "task_id", "") or getattr(task_obj, "id", "")
            title = getattr(task_obj, "title", "")
            status = getattr(task_obj, "status", "")
            due = getattr(task_obj, "due_time", None)
            assignee = getattr(task_obj, "assignment", None) or getattr(task_obj, "assigned_to", None)
        normalized_status = str(status or "").strip().lower()
        is_open = normalized_status in _OPEN_TASK_STATUSES
        return ObjectiveTaskInfo(
            link_id=link.id,
            task_db_id=int(link.task_id),
            strategy_id=link.strategy_id,
            strategy_text=strategy.text if strategy else "",
            task_number=str(task_number),
            title=title,
            status=status,
            due=due,
            assignee=assignee,
            is_open=is_open,
        )
