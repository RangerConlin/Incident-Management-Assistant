from __future__ import annotations

from modules.approvals.models import ApprovalSpec, ApprovalStep
from modules.approvals.spec_registry import register

register(ApprovalSpec(
    entity_type="ics_206",
    steps=(
        ApprovalStep(
            step_id="medl_approval",
            label="Medical Unit Leader",
            role="Medical Unit Leader",
            kind="sequential",
            acceptable_types=("primary", "deputy", "trainee"),
            order=0,
        ),
        ApprovalStep(
            step_id="sofr_approval",
            label="Safety Officer",
            role="Safety Officer",
            kind="sequential",
            acceptable_types=("primary", "deputy"),
            order=1,
        ),
    ),
))
