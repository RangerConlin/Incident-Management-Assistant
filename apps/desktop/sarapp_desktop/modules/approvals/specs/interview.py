from __future__ import annotations

from modules.approvals.models import ApprovalSpec, ApprovalStep
from modules.approvals.spec_registry import register

# Interviews only need an acknowledgment signature — any role, just confirms
# the interview was conducted and documented.

register(ApprovalSpec(
    entity_type="interview",
    steps=(
        ApprovalStep(
            step_id="interviewer_ack",
            label="Interviewer",
            role="",
            kind="ack",
            acceptable_types=(),
            order=0,
        ),
    ),
))
