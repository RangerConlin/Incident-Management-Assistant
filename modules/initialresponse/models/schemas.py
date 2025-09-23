from __future__ import annotations

from pydantic import BaseModel
from typing import Optional


class HastyTaskCreate(BaseModel):
    area: str
    priority: Optional[str] = None
    notes: Optional[str] = None
    create_task: bool = True
    request_logistics: bool = False


class HastyTaskRead(BaseModel):
    id: int
    area: str
    priority: Optional[str] = None
    notes: Optional[str] = None
    operations_task_id: Optional[int] = None
    logistics_request_id: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        orm_mode = True


class ReflexActionCreate(BaseModel):
    trigger: str
    action: Optional[str] = None
    notify: bool = True


class ReflexActionRead(BaseModel):
    id: int
    trigger: str
    action: Optional[str] = None
    communications_alert_id: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        orm_mode = True
