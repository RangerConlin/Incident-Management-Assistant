from __future__ import annotations

from .models import ApprovalSpec

_registry: dict[str, ApprovalSpec] = {}


def register(spec: ApprovalSpec) -> None:
    _registry[spec.entity_type] = spec


def get(entity_type: str) -> ApprovalSpec | None:
    return _registry.get(entity_type)


def all_types() -> list[str]:
    return list(_registry.keys())


# Import specs so they self-register on module load.
from modules.approvals import specs as _specs  # noqa: E402, F401
