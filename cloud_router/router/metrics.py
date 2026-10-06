"""In-memory operational counters for the cloud router.

No external metrics dependency — the router is stateless and single-process
per the architecture doc, so a plain dataclass is sufficient. Exposed via the
``GET /admin/metrics`` endpoint in ``app.py``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class RouterMetrics:
    total_requests: int = 0
    total_request_timeouts: int = 0
    total_request_failures_503: int = 0
    total_request_failures_413: int = 0
    total_ws_channels_opened: int = 0
    total_heartbeat_timeouts: int = 0
    total_register_rejections: int = 0

    def snapshot(self) -> dict[str, Any]:
        return asdict(self)


metrics = RouterMetrics()
