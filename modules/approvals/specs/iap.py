from __future__ import annotations

from modules.approvals.models import ApprovalSpec, ApprovalStep
from modules.approvals.spec_registry import register


def _iap_precondition(incident_id: str, document_id: str) -> bool:
    """All IAP constituent documents must be approved before IC/UC can sign."""
    from utils.api_client import api_client
    try:
        result = api_client.get(
            f"/api/incidents/{incident_id}/iap/{document_id}/readiness"
        )
        return bool(result.get("all_documents_approved", False))
    except Exception:
        return False


register(ApprovalSpec(
    entity_type="iap",
    steps=(
        ApprovalStep(
            step_id="ic_approval",
            label="Incident Commander / Unified Command",
            role="Incident Commander",
            kind="sequential",
            acceptable_types=("primary", "deputy"),
            order=0,
        ),
    ),
    precondition=_iap_precondition,
))
