"""Light theme color library.

This profile consolidates every color token used by the application for the
light appearance.  It merges the legacy palette definitions from
``styles/styles.py`` with the semantic groupings that used to live in
``styles/palette.py`` so downstream modules can source every required color
from a single location.
"""
from __future__ import annotations

from typing import Dict


NAMED_COLORS: Dict[str, str] = {
    # Signature brand blue used for hyperlinks and key interactive affordances.
    "PRIMARY_BLUE": "#1f6feb",
    # Warm accent that highlights secondary actions and warning banners.
    "ACCENT_ORANGE": "#d29922",
    # Default subdued foreground tone for helper text and labels.
    "MUTED_TEXT": "#6e7781",
    # Standard success colour for confirmations and completion badges.
    "SUCCESS_GREEN": "#2da44e",
    # High visibility red for destructive buttons and critical banners.
    "WARNING_RED": "#cf222e",
    # Informational blue used for tooltips and contextual hints.
    "INFO_BLUE": "#338eda",
    # Alert red used for severe errors and blocking callouts.
    "DANGER_RED": "#d64545",
}


# Unified palette used by Qt widgets and adapters.  These colours combine the
# historical palette module entries (bg_window/bg_panel/etc.) with the surface
# colours required by ``styles.styles`` (bg/fg/muted/...).
PALETTE: Dict[str, str] = {
    # Base surface and foreground colours that drive widget backgrounds/text.
    "bg": "#f5f5f5",
    "fg": "#000000",
    "muted": "#666666",
    "accent": "#003a67",
    "success": "#388e3c",
    "warning": "#ffa000",
    "error": "#d32f2f",

    # Window specific surfaces from the semantic palette for legacy widgets.
    "bg_window": "#d1d1d1",
    "bg_panel": "#1313AB",
    "bg_raised": "#74FF0A",
    "fg_primary": "#0F0F0F",
    "fg_muted": "#5A5F6A",

    # Additional semantic accents used by reports and specialty panels.
    "accent_alt": "#27AE60",
    "danger": "#D64545",
    "info": "#338EDA",

    # Control states for button chrome, hover rings, focus outlines, and dividers.
    "ctrl_bg": "#A70C74",
    "ctrl_border": "#D5D8DE",
    "ctrl_hover": "#D6C614",
    "ctrl_focus": "#2F80ED",
    "divider": "#F23333",
}


# Additional semantic groupings from the original palette module are exposed so
# reporting or theming tools can continue to reference them.
SURFACE: Dict[str, str] = {
    "bg_window": PALETTE["bg_window"],
    "bg_panel": PALETTE["bg_panel"],
    "bg_raised": PALETTE["bg_raised"],
    "fg_primary": PALETTE["fg_primary"],
    "fg_muted": PALETTE["fg_muted"],
    "accent": PALETTE["accent"],
    "accent_alt": PALETTE["accent_alt"],
    "warning": PALETTE["warning"],
    "danger": PALETTE["danger"],
    "info": PALETTE["info"],
    "ctrl_bg": PALETTE["ctrl_bg"],
    "ctrl_border": PALETTE["ctrl_border"],
    "ctrl_hover": PALETTE["ctrl_hover"],
    "ctrl_focus": PALETTE["ctrl_focus"],
    "divider": PALETTE["divider"],
}


# Team status colours for Qt table rows and other widgets.  These map the
# lowercase workflow statuses used throughout the operations module.
TEAM_STATUS: Dict[str, Dict[str, str]] = {
    # Air Operations Logging (AOL) state when teams have taken off.
    "aol": {"bg": "#085ec7", "fg": "#e0e0e0"},
    # Unit is arriving on-scene and should stand out on the roster.
    "arrival": {"bg": "#17c4eb", "fg": "#333333"},
    # Unit assigned to a mission but not yet in motion.
    "assigned": {"bg": "#ffeb3b", "fg": "#333333"},
    # Team fully available for tasking.
    "available": {"bg": "#388e3c", "fg": "#ffffff"},
    # Personnel are on a break; purple avoids conflict with tasking colours.
    "break": {"bg": "#9c27b0", "fg": "#333333"},
    # Team briefed but still staged.
    "briefed": {"bg": "#ffeb3b", "fg": "#333333"},
    # Team members resting between deployments.
    "crew rest": {"bg": "#9c27b0", "fg": "#333333"},
    # Team enroute to their assignment.
    "enroute": {"bg": "#ffeb3b", "fg": "#333333"},
    # Unit temporarily unavailable due to equipment or personnel issues.
    "out of service": {"bg": "#d32f2f", "fg": "#333333"},
    # Administrative state while completing reports.
    "report writing": {"bg": "#ce93d8", "fg": "#333333"},
    # Team is returning from the field.
    "returning": {"bg": "#0288d1", "fg": "#e1e1e1"},
    # Time off location (TOL) for aviation teams.
    "tol": {"bg": "#085ec7", "fg": "#e0e0e0"},
    # Aircraft wheels down confirmation.
    "wheels down": {"bg": "#0288d1", "fg": "#e1e1e1"},
    # Mission complete and team in post-incident duties.
    "post incident": {"bg": "#ce93d8", "fg": "#333333"},
    # Teams searching for an assigned subject.
    "find": {"bg": "#ffa000", "fg": "#333333"},
    # Team finished their current assignment.
    "complete": {"bg": "#386a3c", "fg": "#333333"},
}


# Reference team status colours that were historically exposed via
# ``styles/palette.py``.  The uppercase keys map to report/export contexts.
TEAM_STATUS_REFERENCE: Dict[str, Dict[str, str]] = {
    # Print/export friendly hues for available teams.
    "AVAILABLE": {"bg": "#E8F5E9", "fg": "#0E5223"},
    # Reporting colour for assigned state.
    "ASSIGNED": {"bg": "#E3F2FD", "fg": "#0B3A75"},
    # Indicates teams marked as unavailable.
    "OUT_OF_SERVICE": {"bg": "#FDECEA", "fg": "#7A1E1E"},
    # Pending/queued team records in exports.
    "PENDING": {"bg": "#FFF8E1", "fg": "#6A4B00"},
}


TASK_STATUS: Dict[str, Dict[str, str]] = {
    # Draft task exists but is not yet scheduled.
    "created": {"bg": "#6e7b8b", "fg": "#333333"},
    # Logistics has planned the task and is prepping resources.
    "planned": {"bg": "#ce93d8", "fg": "#333333"},
    # Task assigned to a field team.
    "assigned": {"bg": "#ffeb3b", "fg": "#333333"},
    # Team actively working the mission objectives.
    "in progress": {"bg": "#17c4e8", "fg": "#333333"},
    # Task completed successfully.
    "complete": {"bg": "#386a3c", "fg": "#333333"},
    # Task cancelled or stood down.
    "cancelled": {"bg": "#d32f2f", "fg": "#333333"},
}


TASK_STATUS_REFERENCE: Dict[str, Dict[str, str]] = {
    # Colour coding for new tasks in generated documents.
    "NEW": {"bg": "#EEF2FF", "fg": "#1E2A78"},
    # Active/open tasks in exports.
    "ACTIVE": {"bg": "#E6F4EA", "fg": "#0E5223"},
    # Blocked tasks requiring attention.
    "BLOCKED": {"bg": "#FFF1F0", "fg": "#7A1E1E"},
    # Done tasks captured for auditing.
    "DONE": {"bg": "#F1F5F9", "fg": "#1F2937"},
}


TEAM_TYPE_COLORS: Dict[str, str] = {
    # Ground team identifiers.
    "GT": "#228b22",
    # Urban disaster force teams.
    "UDF": "#ffeb3b",
    # Land SAR teams.
    "LSAR": "#228b22",
    # Disaster force (legacy) teams.
    "DF": "#ffeb3b",
    # Combined ground and UAS team.
    "GT/UAS": "#00b987",
    # Combined urban disaster and UAS team.
    "UDF/UAS": "#ffd54f",
    # Uncrewed aerial system units.
    "UAS": "#00cec9",
    # Air assets such as helicopters or planes.
    "AIR": "#00a8ff",
    # Canine teams.
    "K9": "#8b0000",
    # Utility/support teams.
    "UTIL": "#7a7a7a",
}


__all__ = [
    "NAMED_COLORS",
    "PALETTE",
    "SURFACE",
    "TEAM_STATUS",
    "TEAM_STATUS_REFERENCE",
    "TASK_STATUS",
    "TASK_STATUS_REFERENCE",
    "TEAM_TYPE_COLORS",
]

