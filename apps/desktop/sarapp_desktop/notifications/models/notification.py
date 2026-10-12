from dataclasses import dataclass
from typing import Optional, Literal

Severity = Literal['informational', 'routine', 'priority', 'emergency']

# Ordered lowest → highest for threshold comparisons
SEVERITY_RANK: dict[str, int] = {
    'informational': 0,
    'routine':       1,
    'priority':      2,
    'emergency':     3,
}
ToastMode = Literal['auto', 'sticky']
Category = Literal[
    'operations',
    'communications',
    'safety',
    'logistics',
    'planning',
    'administrative',
    'system',
]

# Default toast threshold per category — minimum severity that will show a toast.
# Notifications below this threshold still reach the feed but never pop.
CATEGORY_TOAST_THRESHOLDS: dict[str, str] = {
    'operations':     'routine',
    'communications': 'routine',
    'safety':         'informational',
    'logistics':      'routine',
    'planning':       'routine',
    'administrative': 'priority',
    'system':         'priority',
}

# Category drives toast behavior defaults.
# Callers override toast_mode / toast_duration_ms explicitly if needed.
CATEGORY_DEFAULTS: dict[str, dict] = {
    'operations':     {'toast_mode': 'auto', 'toast_duration_ms': 5000, 'sound': True},
    'communications': {'toast_mode': 'auto', 'toast_duration_ms': 5000, 'sound': True},
    'safety':         {'toast_mode': 'auto', 'toast_duration_ms': 6000, 'sound': True},
    'logistics':      {'toast_mode': 'auto', 'toast_duration_ms': 4000, 'sound': True},
    'planning':       {'toast_mode': 'auto', 'toast_duration_ms': 4000, 'sound': True},
    'administrative': {'toast_mode': 'auto', 'toast_duration_ms': 3000, 'sound': False},
    'system':         {'toast_mode': 'auto', 'toast_duration_ms': 3000, 'sound': False},
}

# Severity overrides toast behavior regardless of category.
# 'show_toast': False suppresses the toast entirely — notification still reaches the feed.
SEVERITY_OVERRIDES: dict[str, dict] = {
    'informational': {'show_toast': False, 'sound': False},
    'routine':       {},
    'priority':      {'toast_duration_ms': 7000},
    'emergency':     {'toast_mode': 'sticky'},
}


@dataclass
class Notification:
    title: str
    message: str
    severity: Severity = 'routine'
    category: Category = 'operations'
    source: str = 'System'
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    # If None, resolved from category + severity defaults at emit time
    toast_mode: Optional[ToastMode] = None
    toast_duration_ms: Optional[int] = None
