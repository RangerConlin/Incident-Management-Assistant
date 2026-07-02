from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .escalation import escalation_chain
from .models import (
    Action,
    ApprovalInstance,
    ApprovalRecord,
    ApprovalStatus,
    StepInstance,
)
from .repository import ApprovalRepository
from . import spec_registry


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ApprovalService:
    def __init__(self, incident_id: str):
        self.incident_id = incident_id
        self.repo = ApprovalRepository(incident_id)

    # ------------------------------------------------------------------
    # Starting the approval process

    def start(self, entity_type: str, entity_id: str) -> ApprovalInstance:
        """Create and activate an approval instance for an entity."""
        spec = spec_registry.get(entity_type)
        if spec is None:
            raise ValueError(f"No approval spec registered for: {entity_type}")

        if spec.precondition and not spec.precondition(self.incident_id, entity_id):
            raise ValueError(
                "Preconditions not met — not all required approvals are complete."
            )

        instance = ApprovalInstance(
            incident_id=self.incident_id,
            entity_type=entity_type,
            entity_id=entity_id,
            status="pending",
            steps=[
                StepInstance(
                    step_id=s.step_id,
                    role=s.role,
                    label=s.label,
                    kind=s.kind,
                    order=s.order,
                )
                for s in spec.steps
            ],
            started_at=_utc_now(),
        )
        self._activate_next_steps(instance)
        self.repo.save_instance(instance)
        return instance

    def get(self, entity_type: str, entity_id: str) -> ApprovalInstance | None:
        return self.repo.get_instance(entity_type, entity_id)

    # ------------------------------------------------------------------
    # Signing

    def can_sign(
        self,
        instance: ApprovalInstance,
        step_id: str,
        person_record: int,
        assignment_type: str,
    ) -> bool:
        step = self._get_step(instance, step_id)
        if step is None or step.status != "active":
            return False
        if step.kind == "ack":
            return True
        if step.resolved_actor_id is not None and step.resolved_actor_id != person_record:
            return False
        spec = spec_registry.get(instance.entity_type)
        if spec is None:
            return False
        spec_step = next((s for s in spec.steps if s.step_id == step_id), None)
        if spec_step and spec_step.acceptable_types:
            return assignment_type in spec_step.acceptable_types
        return True

    def sign(
        self,
        instance: ApprovalInstance,
        step_id: str,
        actor_id: str,
        role_at_time: str,
        assignment_type: str,
        action: Action,
        notes: Optional[str] = None,
    ) -> ApprovalInstance:
        step = self._get_step(instance, step_id)
        if step is None:
            raise ValueError(f"Step not found: {step_id}")
        if step.status != "active":
            raise ValueError(f"Step is not active: {step_id} ({step.status})")

        now = _utc_now()
        step.status = "completed"
        step.completed_at = now

        self.repo.save_record(ApprovalRecord(
            incident_id=self.incident_id,
            entity_type=instance.entity_type,
            entity_id=instance.entity_id,
            step_id=step_id,
            actor_id=actor_id,
            role_at_time=role_at_time,
            assignment_type_at_time=assignment_type,
            action=action,
            timestamp=now,
            notes=notes,
        ))

        if action == "rejected":
            instance.status = "rejected"
            instance.completed_at = now
        else:
            self._advance(instance, now)

        self.repo.save_instance(instance)
        self._write_status_to_entity(instance)
        return instance

    # ------------------------------------------------------------------
    # Inbox query

    def pending_for_person(self, person_record: int) -> list[dict]:
        from modules.command.incident_organization.controller import IncidentOrganizationController
        org = IncidentOrganizationController(self.incident_id)
        assignments = org.list_assignments_for_person(person_record, active_only=True)
        held_roles: set[str] = set()
        for a in assignments:
            pos = org.get_position(a.position_id)
            if pos:
                held_roles.add(pos.title)
        return self.repo.pending_for_roles(list(held_roles), person_record)

    # ------------------------------------------------------------------
    # Internal helpers

    def _get_step(self, instance: ApprovalInstance, step_id: str) -> Optional[StepInstance]:
        return next((s for s in instance.steps if s.step_id == step_id), None)

    def _activate_next_steps(self, instance: ApprovalInstance) -> None:
        completed_orders = {
            s.order for s in instance.steps if s.status == "completed"
        }
        waiting = [s for s in instance.steps if s.status == "waiting"]
        if not waiting:
            return
        min_waiting_order = min(s.order for s in waiting)
        for step in waiting:
            if step.order == min_waiting_order:
                self._activate_step(step)

    def _activate_step(self, step: StepInstance) -> None:
        step.status = "active"
        step.activated_at = _utc_now()
        if step.kind != "ack" and step.role:
            actor_id, resolved_role = self._resolve_actor(step.role)
            step.resolved_actor_id = actor_id
            step.resolved_role = resolved_role
            self._notify_actor(step, actor_id)

    def _notify_actor(self, step: StepInstance, actor_id: Optional[int]) -> None:
        """Alert the current user when an approval step activates for them."""
        if actor_id is None:
            return
        try:
            from utils.state import AppState
            uid = AppState.get_active_user_id()
            if not (uid and str(uid).isdigit() and int(uid) == actor_id):
                return
            from notifications.services import get_notifier
            from notifications.models import Notification
            get_notifier().notify(Notification(
                title="Approval needed",
                message=f"{step.label} is awaiting your approval.",
                severity="priority",
                category="administrative",
                source="Approvals",
                entity_type="approval_step",
                entity_id=step.step_id,
            ))
        except Exception:
            pass

    def _resolve_actor(self, role: str) -> tuple[Optional[str], Optional[str]]:
        from modules.command.incident_organization.controller import IncidentOrganizationController
        org = IncidentOrganizationController(self.incident_id)
        positions = org.list_positions()
        for candidate_role in escalation_chain(role):
            match = next(
                (p for p in positions if p.title == candidate_role and p.status == "active"),
                None,
            )
            if match is None:
                continue
            assignments = org.list_assignments(match.id, active_only=True)
            if assignments:
                return assignments[0].person_record, candidate_role
        return None, None

    def _advance(self, instance: ApprovalInstance, now: str) -> None:
        active_remaining = [s for s in instance.steps if s.status == "active"]
        waiting_remaining = [s for s in instance.steps if s.status == "waiting"]
        if not active_remaining and not waiting_remaining:
            instance.status = "approved"
            instance.completed_at = now
        elif not active_remaining:
            self._activate_next_steps(instance)

    def _write_status_to_entity(self, instance: ApprovalInstance) -> None:
        """Push the terminal approval_status back to the entity's own record."""
        if instance.status not in ("approved", "rejected"):
            return
        from utils.api_client import api_client
        try:
            api_client.patch(
                f"/api/incidents/{self.incident_id}"
                f"/approvals/entity-status/{instance.entity_type}/{instance.entity_id}",
                json={"approval_status": instance.status},
            )
        except Exception:
            pass
