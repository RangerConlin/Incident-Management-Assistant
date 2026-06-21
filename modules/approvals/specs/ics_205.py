from __future__ import annotations

from modules.approvals.models import ApprovalSpec, ApprovalStep
from modules.approvals.spec_registry import register

register(ApprovalSpec(
    entity_type="ics_205",
    steps=(
        ApprovalStep(
            step_id="coml_signoff",
            label="Communications Unit Leader",
            role="Communications Unit Leader",
            kind="sequential",
            acceptable_types=("primary", "deputy", "trainee"),
            order=0,
        ),
    ),
))
