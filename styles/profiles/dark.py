"""Dark theme color library.

The dark profile mirrors the structure of :mod:`styles.profiles.light` while
providing darker surface values and higher contrast foreground selections.
"""
from __future__ import annotations

from typing import Dict


NAMED_COLORS: Dict[str, str] = {
    # Core hyperlink and focus colour tuned for dark backgrounds.
    "PRIMARY_BLUE": "#58a6ff",
    # Shared accent orange for complementary highlights.
    "ACCENT_ORANGE": "#d29922",
    # Muted descriptive text for labels or placeholder copy.
    "MUTED_TEXT": "#8b949e",
    # Positive confirmation and health indicators.
    "SUCCESS_GREEN": "#3fb950",
    # Alert tone for risky operations that should pop on dark UI.
    "WARNING_RED": "#f0883e",
    # Soft blue for neutral information and assistive hints.
    "INFO_BLUE": "#5eb0ef",
    # Strong error colour for blocking states.
    "DANGER_RED": "#e5484d",
}


PALETTE: Dict[str, str] = {
    # Core surfaces/foregrounds consumed by the Qt palette helpers.
    "bg": "#2c2c2c",
    "fg": "#b4b4b4",
    "muted": "#888888",
    "accent": "#90caf9",
    "success": "#4caf50",
    "warning": "#ffb300",
    "error": "#ef5350",

    # Semantic window surfaces used by the legacy styling helpers.
    "bg_window": "#0F1115",
    "bg_panel": "#151821",
    "bg_raised": "#1B1F2A",
    "fg_primary": "#ECEFF4",
    "fg_muted": "#A4ADBA",

    # Secondary accent and message tones for reports and charts.
    "accent_alt": "#4CC38A",
    "danger": "#E5484D",
    "info": "#5EB0EF",

    # Control chrome states for hover/focus feedback and separators.
    "ctrl_bg": "#1B1F2A",
    "ctrl_border": "#2A2F3A",
    "ctrl_hover": "#212737",
    "ctrl_focus": "#5CA3FF",
    "divider": "#242A36",
}


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


TEAM_STATUS: Dict[str, Dict[str, str]] = {
    # Air Operations Logging state showing aircraft in the air.
    "aol": {"bg": "#0b3d75", "fg": "#f5f5f5"},
    # Unit is arriving at the incident base or scene.
    "arrival": {"bg": "#1f6088", "fg": "#f0f0f0"},
    # Tasked but still staged or briefing.
    "assigned": {"bg": "#a88f1a", "fg": "#f5f5f5"},
    # Team ready to accept work.
    "available": {"bg": "#2f6d34", "fg": "#f5f5f5"},
    # Scheduled break downtime for the team.
    "break": {"bg": "#6e2b75", "fg": "#f5f5f5"},
    # Briefed and awaiting movement orders.
    "briefed": {"bg": "#a88f1a", "fg": "#f5f5f5"},
    # Resting crews off-shift.
    "crew rest": {"bg": "#6e2b75", "fg": "#f5f5f5"},
    # Travelling to the operational area.
    "enroute": {"bg": "#a88f1a", "fg": "#f5f5f5"},
    # Unable to respond due to equipment or member limitations.
    "out of service": {"bg": "#8c2f2f", "fg": "#f5f5f5"},
    # Completing paperwork and documentation.
    "report writing": {"bg": "#785b8f", "fg": "#f5f5f5"},
    # Returning from the field post assignment.
    "returning": {"bg": "#1f6088", "fg": "#f5f5f5"},
    # Time off location indicator.
    "tol": {"bg": "#0b3d75", "fg": "#f5f5f5"},
    # Aircraft landing confirmation.
    "wheels down": {"bg": "#1f6088", "fg": "#f5f5f5"},
    # Post mission debrief/cleanup state.
    "post incident": {"bg": "#785b8f", "fg": "#f5f5f5"},
    # Active search for subject.
    "find": {"bg": "#b2700d", "fg": "#f5f5f5"},
    # Assignment wrapped up successfully.
    "complete": {"bg": "#2f6d34", "fg": "#f5f5f5"},
}


TEAM_STATUS_REFERENCE: Dict[str, Dict[str, str]] = {
    # Export palette for teams flagged as available.
    "AVAILABLE": {"bg": "#1E3A2A", "fg": "#E0FFE8"},
    # Assigned roster entries in PDF/report contexts.
    "ASSIGNED": {"bg": "#132C49", "fg": "#E5F1FF"},
    # Out of service teams in dark theme exports.
    "OUT_OF_SERVICE": {"bg": "#4A1C1C", "fg": "#FBD7D7"},
    # Pending/queued team entries.
    "PENDING": {"bg": "#3B2A08", "fg": "#FFEFD2"},
}


TASK_STATUS: Dict[str, Dict[str, str]] = {
    # Placeholder task awaiting planning details.
    "created": {"bg": "#444c55", "fg": "#f5f5f5"},
    # Logistics is preparing or staging the assignment.
    "planned": {"bg": "#6d5478", "fg": "#f5f5f5"},
    # Task has an assigned operational team.
    "assigned": {"bg": "#a88f1a", "fg": "#f5f5f5"},
    # Team executing the objectives in the field.
    "in progress": {"bg": "#1f6088", "fg": "#f5f5f5"},
    # Task successfully concluded.
    "complete": {"bg": "#2f6d34", "fg": "#f5f5f5"},
    # Task cancelled or reassigned elsewhere.
    "cancelled": {"bg": "#8c2f2f", "fg": "#f5f5f5"},
}


TASK_STATUS_REFERENCE: Dict[str, Dict[str, str]] = {
    # New task indicator in printed outputs.
    "NEW": {"bg": "#202741", "fg": "#D9E2FF"},
    # Active task highlight.
    "ACTIVE": {"bg": "#1F3A28", "fg": "#DFF5E7"},
    # Blocked task warning colour.
    "BLOCKED": {"bg": "#3F1E1E", "fg": "#FFD9D9"},
    # Completed task colourway.
    "DONE": {"bg": "#1F2731", "fg": "#E2E8F0"},
}


TEAM_TYPE_COLORS: Dict[str, str] = {
    # Ground team identifiers.
    "GT": "#2f6d34",
    # Urban disaster force teams.
    "UDF": "#bfa523",
    # Land SAR units.
    "LSAR": "#2f6d34",
    # Disaster force shorthand.
    "DF": "#bfa523",
    # Combined ground and UAS capabilities.
    "GT/UAS": "#2d8f6d",
    # Combined urban disaster force and UAS teams.
    "UDF/UAS": "#c59b3f",
    # Uncrewed aerial systems.
    "UAS": "#1f7a83",
    # Aviation assets.
    "AIR": "#3583c4",
    # Canine units.
    "K9": "#a03a3a",
    # Utility/support resources.
    "UTIL": "#5a5a5a",
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

