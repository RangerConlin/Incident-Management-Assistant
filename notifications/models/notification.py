from dataclasses import dataclass
from typing import Optional, Literal

Severity = Literal['info', 'success', 'warning', 'error']
ToastMode = Literal['auto', 'sticky']


@dataclass
class Notification:
    title: str
    message: str
    severity: Severity = 'info'
    source: str = 'System'
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    toast_mode: Optional[ToastMode] = None
    toast_duration_ms: Optional[int] = None
