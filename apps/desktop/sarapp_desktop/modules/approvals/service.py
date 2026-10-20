from __future__ import annotations

from typing import Optional

from .models import ApprovalInstance, Action, StepInstance
from .repository import ApprovalRepository


class ApprovalService:
    def __init__(self, incident_id: str):
        self.incident_id = incident_id
        self.repo = ApprovalRepository(incident_id)

    # ------------------------------------------------------------------
    # Starting the approval process

    def start(self, entity_type: str, entity_id: str) -> ApprovalInstance:
        instance = self.repo.start(entity_type, entity_id)
        self._notify_awaiting_me(instance)
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
        """Best-effort UI hint — the sign endpoint is the real authority."""
        step = self._get_step(instance, step_id)
        if step is None or step.status != "active":
            return False
        if step.kind == "ack":
            return True
        return step.resolved_actor_id == person_record

    def sign(
        self,
        instance: ApprovalInstance,
        step_id: str,
        actor_id: int,
        action: Action,
        notes: Optional[str] = None,
    ) -> ApprovalInstance:
        updated = self.repo.sign(instance.entity_type, instance.entity_id, step_id, actor_id, action, notes)
        self._notify_awaiting_me(updated)
        return updated

    def assignment_type_for(self, person_record: int) -> str:
        """Assignment type (primary/deputy/trainee) of a person's active assignment."""
        from modules.command.incident_organization.controller import IncidentOrganizationController
        org = IncidentOrganizationController(self.incident_id)
        assignments = org.list_assignments_for_person(person_record, active_only=True)
        if assignments:
            return getattr(assignments[0], "assignment_type", "primary") or "primary"
        return "primary"

    # ------------------------------------------------------------------
    # Inbox query

    def pending_for_person(self, person_record: int) -> list[dict]:
        return self.repo.pending_for_person(person_record)

    def assign_step(self, instance: ApprovalInstance, step_id: str, actor_id: int) -> ApprovalInstance:
        """Manually pick who should act on a step nobody is resolved for yet."""
        updated = self.repo.assign_step(instance.entity_type, instance.entity_id, step_id, actor_id)
        self._notify_awaiting_me(updated)
        return updated

    # ------------------------------------------------------------------
    # Internal helpers

    def _get_step(self, instance: ApprovalInstance, step_id: str) -> Optional[StepInstance]:
        return next((s for s in instance.steps if s.step_id == step_id), None)

    def _notify_awaiting_me(self, instance: ApprovalInstance) -> None:
        """Alert the current user when an approval step is now active for them."""
        try:
            from utils.state import AppState
            uid = AppState.get_active_user_id()
            if not (uid and str(uid).isdigit()):
                return
            person_record = int(uid)
        except Exception:
            return
        for step in instance.steps:
            if step.status == "active" and step.resolved_actor_id == person_record:
                try:
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
