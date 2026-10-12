from __future__ import annotations

from modules.approvals.models import ApprovalSpec, ApprovalStep
from modules.approvals.spec_registry import register

# IWI reports require parallel sign-off from Safety Officer and the IC.
# Both must sign; order doesn't matter.

register(ApprovalSpec(
    entity_type="iwi_report",
    steps=(
        ApprovalStep(
            step_id="sofr_signoff",
            label="Safety Officer",
            role="Safety Officer",
            kind="parallel",
            acceptable_types=("primary", "deputy"),
            order=0,
        ),
        ApprovalStep(
            step_id="ic_signoff",
            label="Incident Commander",
            role="Incident Commander",
            kind="parallel",
            acceptable_types=("primary", "deputy"),
            order=0,
        ),
    ),
))
