from __future__ import annotations

# Authoritative lists for dropdowns and simple validation.
# Keep these in sync with ops/planning docs.

CATEGORIES = [
    "<New Task>",
    "Air SAR",
    "Damage Assessment",
    "Ground SAR",
    "Logistics Support",
    "Other",
    "Photography",
    "Relocation",
]

PRIORITIES = ["Low", "Medium", "High", "Critical"]

TASK_STATUSES = ["Draft", "Planned", "In Progress", "Completed", "Cancelled"]

# Team status options vary by category/type when displayed in the Teams tab
TEAM_STATUS_BY_CATEGORY = {
    "Air SAR": [
        "Assigned", "Briefed", "En Route", "On Scene", "Discovery/Find", "Complete", "RTB"
    ],
    "Ground SAR": [
        "Assigned", "Briefed", "En Route", "On Scene", "Discovery/Find", "Complete", "RTB"
    ],
    "Logistics Support": [
        "Assigned", "En Route", "On Scene", "Complete"
    ],
    "Damage Assessment": [
        "Assigned", "En Route", "On Scene", "Complete"
    ],
    "Photography": [
        "Assigned", "En Route", "On Scene", "Complete"
    ],
    "Relocation": [
        "Assigned", "En Route", "On Scene", "Complete"
    ],
    "Other": [
        "Assigned", "En Route", "On Scene", "Complete"
    ],
    "<New Task>": [
        "Assigned", "En Route", "On Scene", "Complete"
    ],
}

# Utility helpers

def team_statuses_for_category(category: str) -> list[str]:
    return TEAM_STATUS_BY_CATEGORY.get(category, TEAM_STATUS_BY_CATEGORY["Other"])

