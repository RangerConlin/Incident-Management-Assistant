from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal, Optional


# ---------------------------------------------------------------------------
# Spec layer — defined in code, never stored in the database
# ---------------------------------------------------------------------------

StepKind = Literal["sequential", "parallel", "ack"]
Action = Literal["approved", "rejected", "acknowledged"]


@dataclass(frozen=True)
class ApprovalStep:
    """One node in an approval spec."""

    step_id: str
    label: str
    role: str
    kind: StepKind = "sequential"
    # Which assignment_types are allowed to sign. Empty list means any type.
    acceptable_types: tuple[str, ...] = ()
    # Steps with the same order value activate together (parallel group).
    order: int = 0


@dataclass(frozen=True)
class ApprovalSpec:
    """Full approval definition for one entity type."""

    entity_type: str
    steps: tuple[ApprovalStep, ...]
    # Optional callable(incident_id, entity_id) -> bool checked before
    # the first step can be activated. Used for composite gates like the IAP.
    precondition: Optional[Callable[[str, str], bool]] = field(default=None, compare=False, hash=False)


# ---------------------------------------------------------------------------
# Instance layer — lives in approval_instances collection, keyed by
# (incident_id, entity_type, entity_id)
# ---------------------------------------------------------------------------

StepStatus = Literal["waiting", "active", "completed", "skipped"]
ApprovalStatus = Literal["not_started", "pending", "approved", "rejected"]


@dataclass
class StepInstance:
    step_id: str
    role: str
    label: str
    kind: StepKind
    order: int
    status: StepStatus = "waiting"
    resolved_actor_id: Optional[str] = None
    resolved_role: Optional[str] = None  # may differ from role if escalated
    activated_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "role": self.role,
            "label": self.label,
            "kind": self.kind,
            "order": self.order,
            "status": self.status,
            "resolved_actor_id": self.resolved_actor_id,
            "resolved_role": self.resolved_role,
            "activated_at": self.activated_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> StepInstance:
        return cls(
            step_id=d["step_id"],
            role=d["role"],
            label=d["label"],
            kind=d.get("kind", "sequential"),
            order=d.get("order", 0),
            status=d.get("status", "waiting"),
            resolved_actor_id=d.get("resolved_actor_id"),
            resolved_role=d.get("resolved_role"),
            activated_at=d.get("activated_at"),
            completed_at=d.get("completed_at"),
        )


@dataclass
class ApprovalInstance:
    """One approvable entity's full approval chain state."""

    incident_id: str
    entity_type: str
    entity_id: str
    status: ApprovalStatus = "not_started"
    steps: list[StepInstance] = field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "incident_id": self.incident_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "status": self.status,
            "steps": [s.to_dict() for s in self.steps],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ApprovalInstance:
        return cls(
            incident_id=d["incident_id"],
            entity_type=d["entity_type"],
            entity_id=d["entity_id"],
            status=d.get("status", "not_started"),
            steps=[StepInstance.from_dict(s) for s in d.get("steps", [])],
            started_at=d.get("started_at"),
            completed_at=d.get("completed_at"),
        )


# ---------------------------------------------------------------------------
# Record layer — separate collection, append-only audit trail
# ---------------------------------------------------------------------------

@dataclass
class ApprovalRecord:
    incident_id: str
    entity_type: str
    entity_id: str
    step_id: str
    actor_id: str
    role_at_time: str
    assignment_type_at_time: str
    action: Action
    timestamp: str
    notes: Optional[str] = None
