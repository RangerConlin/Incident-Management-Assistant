from __future__ import annotations

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List

from modules.planning.models.objectives import Objective, ObjectiveComment, AuditLog

router = APIRouter(prefix="/api/planning/objectives", tags=["planning-objectives"])

# In-memory stores for demonstration purposes
_OBJECTIVES: Dict[int, Objective] = {}
_COMMENTS: Dict[int, List[ObjectiveComment]] = {}
_LOGS: Dict[int, List[AuditLog]] = {}
_next_id = 1


@router.get("")
def list_objectives() -> Dict[str, Any]:
    """Return all objectives currently in memory."""
    return {"objectives": list(_OBJECTIVES.values())}


@router.post("")
def create_objective(payload: Dict[str, Any]) -> Objective:
    """Create a new objective."""
    global _next_id
    obj = Objective(
        id=_next_id,
        mission_id=payload.get("mission_id", 1),
        description=payload.get("description", ""),
        status="Pending",
        priority=payload.get("priority", "Normal"),
        created_by=payload.get("created_by", 0),
        created_at=payload.get("created_at", ""),
    )
    _OBJECTIVES[obj.id] = obj
    _COMMENTS[obj.id] = []
    _LOGS[obj.id] = []
    _next_id += 1
    return obj


@router.put("/{obj_id}")
def update_objective(obj_id: int, payload: Dict[str, Any]) -> Objective:
    obj = _OBJECTIVES.get(obj_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Objective not found")
    for field_name in ["description", "priority", "customer", "due_time"]:
        if field_name in payload:
            setattr(obj, field_name, payload[field_name])
    return obj


@router.post("/{obj_id}/status")
def set_status(obj_id: int, payload: Dict[str, Any]) -> Objective:
    obj = _OBJECTIVES.get(obj_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Objective not found")
    status = payload.get("status")
    if not status:
        raise HTTPException(status_code=400, detail="Missing status")
    obj.status = status
    return obj


@router.post("/{obj_id}/comment")
def add_comment(obj_id: int, payload: Dict[str, Any]) -> ObjectiveComment:
    comments = _COMMENTS.setdefault(obj_id, [])
    comment = ObjectiveComment(
        id=len(comments) + 1,
        objective_id=obj_id,
        user_id=payload.get("user_id", 0),
        timestamp=payload.get("timestamp", ""),
        text=payload.get("text", ""),
        parent_id=payload.get("parent_id"),
    )
    comments.append(comment)
    return comment


@router.get("/{obj_id}/history")
def get_history(obj_id: int) -> Dict[str, Any]:
    return {"logs": _LOGS.get(obj_id, [])}
