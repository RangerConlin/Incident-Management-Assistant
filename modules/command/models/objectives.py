from __future__ import annotations

"""Incident Objectives data access layer for the Command module."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Sequence


PRIORITY_VALUES = ["low", "normal", "high", "urgent"]
STATUS_VALUES = ["draft", "active", "deferred", "completed", "cancelled"]


@dataclass(slots=True)
class ObjectiveTaskInfo:
    """A task linked directly to an objective (Tasks tab row)."""

    link_id: int
    task_db_id: int
    task_number: str
    title: str
    status: str
    due: str | None
    assignee: str | None
    is_open: bool


@dataclass(slots=True)
class ObjectiveAuditEntry:
    """A single audit log row for the Log tab."""

    ts: str
    action: str
    field: str | None
    old_value: str | None
    new_value: str | None
    user_id: str | None


@dataclass(slots=True)
class ObjectiveSummary:
    """Summary row exposed to the table model."""

    id: str
    code: str
    text: str
    priority: str
    status: str
    owner_section: str | None
    tags: list[str]
    op_period_id: str | None
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


_OPEN_TASK_STATUSES = {"created", "draft", "planned", "assigned", "in progress"}


# ---------------------------------------------------------------------------
# MongoDB-backed repository — used by all UI code after the SQLite cutover.
# ---------------------------------------------------------------------------

class ApiObjectiveRepository:
    """Incident objective repository backed by the SARApp API (MongoDB)."""

    def __init__(self, incident_id: str) -> None:
        self.incident_id = str(incident_id)

    # ------------------------------------------------------------------
    # Objectives

    def list_objectives(self, filters: ObjectiveFilters | None = None) -> list[ObjectiveSummary]:
        from utils.api_client import api_client
        params: dict = {"incident_id": self.incident_id}
        if filters:
            if filters.search:
                params["search"] = filters.search
            if filters.op_period_id is not None:
                params["op_period_id"] = str(filters.op_period_id)
            if filters.status:
                params["status"] = list(filters.status)[0]
            if filters.priority:
                params["priority"] = list(filters.priority)[0]
        docs = api_client.get("/api/objectives", params=params) or []
        return [self._doc_to_summary(d) for d in docs]

    def create_objective(self, payload: dict, user_id: str | None = None) -> "ObjectiveDetail":
        from utils.api_client import api_client
        body = {
            "incident_id": self.incident_id,
            "text": payload.get("text", "").strip(),
            "priority": payload.get("priority", "normal"),
            "status": payload.get("status", "draft"),
            "owner_section": payload.get("owner_section"),
            "op_period_id": payload.get("op_period_id"),
            "tags": list(payload.get("tags") or []),
            "created_by": user_id,
        }
        if payload.get("narrative"):
            body["narrative"] = payload["narrative"]
        if payload.get("origin_module"):
            body["origin_module"] = payload["origin_module"]
        if payload.get("origin_id"):
            body["origin_id"] = payload["origin_id"]
        doc = api_client.post("/api/objectives", json=body)
        return self.get_objective_detail(doc["_id"])

    def update_objective(self, objective_id: str, payload: dict, user_id: str | None = None) -> "ObjectiveDetail":
        from utils.api_client import api_client
        body: dict = {"updated_by": user_id}
        for key in ("text", "priority", "status", "owner_section", "tags", "op_period_id", "narrative"):
            if key in payload:
                body[key] = payload[key]
        api_client.patch(
            f"/api/objectives/{objective_id}",
            json=body,
            params={"incident_id": self.incident_id},
        )
        return self.get_objective_detail(objective_id)

    def set_status(self, objective_id: str, status: str, user_id: str | None = None) -> "ObjectiveDetail":
        return self.update_objective(objective_id, {"status": status}, user_id=user_id)

    def reorder_objectives(self, ordered_ids: list[str], user_id: str | None = None) -> None:
        from utils.api_client import api_client
        api_client.post(
            f"/api/objectives/reorder?incident_id={self.incident_id}",
            json={"ids": [str(i) for i in ordered_ids]},
        )

    def get_objective_detail(self, objective_id: str) -> "ObjectiveDetail":
        from utils.api_client import api_client
        doc = api_client.get(
            f"/api/objectives/{objective_id}",
            params={"incident_id": self.incident_id},
        )
        summary = self._doc_to_summary(doc)
        tasks = self.list_tasks(objective_id)
        summary.total_tasks = len(tasks)
        summary.open_tasks = sum(1 for t in tasks if t.is_open)
        return ObjectiveDetail(
            summary=summary,
            tasks=tasks,
            narrative=doc.get("narrative"),
        )

    def export_ics202(self) -> dict:
        objectives = []
        for summary in self.list_objectives():
            objectives.append({
                "order": summary.display_order,
                "code": summary.code,
                "text": summary.text,
                "priority": summary.priority,
                "status": summary.status,
            })
        return {"operational_period": {}, "objectives": objectives}

    # ------------------------------------------------------------------
    # Task links — tasks tied directly to this objective. Tasks tied to a
    # work assignment ("strategy") live and are managed in the Tactics &
    # Resource Planner instead; see WorkAssignmentRepository.

    def list_tasks(self, objective_id: str) -> list[ObjectiveTaskInfo]:
        from utils.api_client import api_client
        try:
            links = api_client.get(
                f"/api/objectives/{objective_id}/tasks",
                params={"incident_id": self.incident_id},
            ) or []
        except Exception:
            return []
        return [self._link_to_task_info(link) for link in links]

    def link_task(self, objective_id: str, task_id: int, user_id: str | None = None) -> dict:
        from utils.api_client import api_client
        try:
            return api_client.post(
                f"/api/objectives/{objective_id}/tasks",
                json={"task_id": task_id, "created_by": user_id},
                params={"incident_id": self.incident_id},
            )
        except Exception:
            return {}

    def unlink_task(self, objective_id: str, link_id: int) -> None:
        from utils.api_client import api_client
        try:
            api_client.delete(
                f"/api/objectives/{objective_id}/tasks/{link_id}",
                params={"incident_id": self.incident_id},
            )
        except Exception:
            pass

    def list_history(self, objective_id: str) -> list[ObjectiveAuditEntry]:
        from utils.api_client import api_client
        try:
            entries = api_client.get(
                f"/api/objectives/{objective_id}/audit",
                params={"incident_id": self.incident_id},
            ) or []
        except Exception:
            return []
        return [
            ObjectiveAuditEntry(
                ts=e.get("ts", ""),
                action=e.get("action", ""),
                field=e.get("field"),
                old_value=e.get("old_value"),
                new_value=e.get("new_value"),
                user_id=e.get("user_id"),
            )
            for e in entries
        ]

    # ------------------------------------------------------------------
    # Internal

    @staticmethod
    def _link_to_task_info(link: dict) -> ObjectiveTaskInfo:
        task_id = int(link.get("task_id") or 0)
        task_info = ApiObjectiveRepository._fetch_task_info(task_id)
        status = str(task_info.get("status") or "")
        return ObjectiveTaskInfo(
            link_id=int(link.get("id") or 0),
            task_db_id=task_id,
            task_number=str(task_info.get("task_number") or task_id),
            title=str(task_info.get("title") or ""),
            status=status,
            due=task_info.get("due"),
            assignee=task_info.get("assignee"),
            is_open=status.strip().lower() in _OPEN_TASK_STATUSES,
        )

    @staticmethod
    def _fetch_task_info(task_id: int) -> dict:
        from utils.api_client import api_client
        from utils.incident_context import get_active_incident_id
        iid = get_active_incident_id()
        if not iid:
            return {}
        try:
            doc = api_client.get(f"/api/incidents/{iid}/operations/tasks/{task_id}")
        except Exception:
            return {}
        if not doc:
            return {}
        return {
            "task_number": doc.get("task_id") or doc.get("id"),
            "title": doc.get("title", ""),
            "status": doc.get("status", ""),
            "due": doc.get("due_time"),
            "assignee": doc.get("assignment") or doc.get("assigned_to"),
        }

    @staticmethod
    def _doc_to_summary(doc: dict) -> ObjectiveSummary:
        updated_at: datetime | None = None
        raw_ts = doc.get("updated_at")
        if raw_ts:
            try:
                ts = raw_ts.replace("Z", "+00:00")
                dt = datetime.fromisoformat(ts)
                updated_at = dt.replace(tzinfo=None) if dt.tzinfo is not None else dt
            except Exception:
                pass
        return ObjectiveSummary(
            id=doc["_id"],
            code=doc.get("code") or doc.get("objective_id") or doc["_id"],
            text=doc.get("text") or doc.get("description") or "",
            priority=(doc.get("priority") or "normal").lower(),
            status=(doc.get("status") or "draft").lower(),
            owner_section=doc.get("owner_section") or doc.get("assigned_section"),
            tags=doc.get("tags") or doc.get("tags_json") or [],
            op_period_id=doc.get("op_period_id"),
            updated_at=updated_at,
            updated_by=doc.get("updated_by"),
            display_order=int(doc.get("display_order") or 0),
        )
