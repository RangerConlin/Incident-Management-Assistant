"""Public API helpers for the simplified check-in service."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .services import (
    CheckInService,
    ENTITY_CONFIG,
    ENTITY_ORDER,
    EntityConfig,
    FieldSpec,
    get_entity_config,
    get_service,
    iter_entity_configs,
)


def list_master_records(entity_type: str) -> List[Dict[str, Any]]:
    """Return master records for ``entity_type`` using the shared service."""

    return get_service().list_master_records(entity_type)


def search_master_records(
    entity_type: str, query: str, limit: int = 50
) -> List[Dict[str, Any]]:
    """Search master records that match ``query``."""

    return get_service().search_master_records(entity_type, query, limit)


def check_in(
    entity_type: str, record_id: Any, overrides: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Duplicate ``record_id`` from the master table into the incident DB."""

    return get_service().check_in(entity_type, record_id, overrides=overrides)


def create_master_record(entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new master record for ``entity_type`` and return it."""

    return get_service().create_master_record(entity_type, data)


__all__ = [
    "CheckInService",
    "ENTITY_CONFIG",
    "ENTITY_ORDER",
    "EntityConfig",
    "FieldSpec",
    "check_in",
    "create_master_record",
    "get_entity_config",
    "get_service",
    "iter_entity_configs",
    "list_master_records",
    "search_master_records",
]
