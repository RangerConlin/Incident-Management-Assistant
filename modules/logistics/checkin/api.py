"""Compatibility façade that proxies to :mod:`modules.logistics.checkin.services`."""
from __future__ import annotations

from .services import (
    CheckInService,
    apply_rules,
    flushOfflineQueue,
    flush_offline_queue,
    getHistory,
    getRoster,
    get_service,
    listRoles,
    listTeams,
    pendingQueueCount,
    searchPersonnel,
    setOffline,
    upsertCheckIn,
)

__all__ = [
    "CheckInService",
    "apply_rules",
    "flushOfflineQueue",
    "flush_offline_queue",
    "getHistory",
    "getRoster",
    "get_service",
    "listRoles",
    "listTeams",
    "pendingQueueCount",
    "searchPersonnel",
    "setOffline",
    "upsertCheckIn",
]
