"""Helpers for Public Information release lifecycle behavior."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ACTIONABLE_STATUSES = {
    "Draft",
    "Pending Approval",
    "Returned for Revision",
    "Published",
    "Needs Corrections",
}

APPROVAL_HISTORY_STATUSES = {
    "Pending Approval",
    "Approved",
    "Published",
    "Needs Corrections",
    "Archived",
}


@dataclass(frozen=True, slots=True)
class LifecycleAction:
    key: str
    label: str
    target_status: str | None = None
    requires_comment: bool = False
    opens_copy: bool = False


_ACTIONS_BY_STATUS: dict[str, list[LifecycleAction]] = {
    "Draft": [
        LifecycleAction("save_draft", "Save Draft"),
        LifecycleAction("submit_for_approval", "Submit for Approval", "Pending Approval"),
    ],
    "Pending Approval": [
        LifecycleAction("approve", "Approve", "Approved"),
        LifecycleAction("return_for_revision", "Return for Revision", "Returned for Revision"),
    ],
    "Returned for Revision": [
        LifecycleAction("save_draft", "Save Draft"),
        LifecycleAction("resubmit_for_approval", "Resubmit for Approval", "Pending Approval"),
    ],
    "Approved": [
        LifecycleAction("publish_release", "Publish / Release", "Published"),
        LifecycleAction("return_for_revision", "Return for Revision", "Returned for Revision"),
    ],
    "Published": [
        LifecycleAction("create_update", "Create Update", opens_copy=True),
        LifecycleAction("flag_corrections", "Flag Corrections", "Needs Corrections"),
        LifecycleAction("archive", "Archive", "Archived"),
    ],
    "Needs Corrections": [
        LifecycleAction("save_correction_draft", "Save Correction Draft"),
        LifecycleAction("submit_correction_for_approval", "Submit Correction for Approval", "Pending Approval"),
    ],
}


def lifecycle_actions_for_status(status: str) -> list[LifecycleAction]:
    return list(_ACTIONS_BY_STATUS.get(status, []))


def is_actionable_status(status: str) -> bool:
    return status in ACTIONABLE_STATUSES


def approval_history_rows(approvals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in approvals if row.get("action") in APPROVAL_HISTORY_STATUSES]

