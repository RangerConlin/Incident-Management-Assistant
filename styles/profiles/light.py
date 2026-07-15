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

PALETTE: Dict[str, str] = {
    # Base surface and foreground colours that drive widget backgrounds/text.
    "bg":           "#f5f5f5",
    "fg":           "#000000",
    "muted":        "#666666",
    "accent":       "#003a67",
    "success":      "#388e3c",
    "warning":      "#ffa000",
    "error":        "#d32f2f",

    # Window specific surfaces from the semantic palette for legacy widgets.
    # Lightness ladder (lightest -> darkest): bg_window > dock_tab_bg > bg_raised >
    # menu_bar_bg > bg_panel, with a slight cool tint to soften pure-gray contrast,
    # mirroring the dark profile's darkest -> lightest ladder in reverse.
    "bg_window":    "#E4E4E4",
    "bg_panel":     "#B8B8BC",
    "menu_bar_bg":  "#C2C2C6",
    "bg_raised":    "#CACACE",
    "fg_primary":   "#1A1A1A",
    "fg_muted":     "#5A5F6A",
    "dock_tab_bg":  "#D6D6DA",

    # Additional semantic accents used by reports and specialty panels.
    "accent_alt":   "#27AE60",
    "danger":       "#D64545",
    "info":         "#338EDA",

    # Control states for button chrome, hover rings, focus outlines, and dividers.
    "ctrl_bg":      "#EFEFF1",
    "ctrl_border":  "#D8DADD",
    "ctrl_hover":   "#E3E5E8",
    "ctrl_focus":   "#2F80ED",
    "divider":      "#D8DADD",

    # Buttons
    "btn_bg":       "#EFEFF1",
    "btn_border":   "#D8DADD",
    "btn_hover":    "#E3E5E8",
    "btn_focus":    "#2F80ED",
    "btn_disabled": "#D2D4D7",
    "btn_checked":  "#2F80ED",
}

# Additional semantic groupings from the original palette module are exposed so
# reporting or theming tools can continue to reference them.
SURFACE: Dict[str, str] = {
    # Window specific surfaces from the semantic palette for legacy widgets.
    "bg_window": PALETTE["bg_window"],
    "bg_panel": PALETTE["bg_panel"],
    "menu_bar_bg": PALETTE["menu_bar_bg"],
    "bg_raised": PALETTE["bg_raised"],
    "fg_primary": PALETTE["fg_primary"],
    "fg_muted": PALETTE["fg_muted"],
    "dock_tab_bg": PALETTE["dock_tab_bg"],
    # Additional semantic accents used by reports and specialty panels.
    "accent": PALETTE["accent"],
    "accent_alt": PALETTE["accent_alt"],
    "warning": PALETTE["warning"],
    "danger": PALETTE["danger"],
    "info": PALETTE["info"],
    # Control states for button chrome, hover rings, focus outlines, and dividers.
    "ctrl_bg": PALETTE["ctrl_bg"],
    "ctrl_border": PALETTE["ctrl_border"],
    "ctrl_hover": PALETTE["ctrl_hover"],
    "ctrl_focus": PALETTE["ctrl_focus"],
    "divider": PALETTE["divider"],
    # Buttons
    "btn_bg": PALETTE["btn_bg"],
    "btn_border": PALETTE["btn_border"],
    "btn_hover": PALETTE["btn_hover"],
    "btn_focus": PALETTE["btn_focus"],
    "btn_disabled": PALETTE["btn_disabled"],
    "btn_checked": PALETTE["btn_checked"],
}

# Team status colours for Qt table rows and other widgets.  These map the
# lowercase workflow statuses used throughout the operations module.
TEAM_STATUS: Dict[str, Dict[str, str]] = {
    "aol":              {"bg": "#1565C0", "fg": "#ffffff"},
    "arrival":          {"bg": "#00B8D4", "fg": "#1a1a1a"},
    "assigned":         {"bg": "#FFC107", "fg": "#1a1a1a"},
    "available":        {"bg": "#43A047", "fg": "#ffffff"},
    "break":            {"bg": "#AB47BC", "fg": "#ffffff"},
    "briefed":          {"bg": "#FFC107", "fg": "#1a1a1a"},
    "crew rest":        {"bg": "#AB47BC", "fg": "#ffffff"},
    "enroute":          {"bg": "#1aa8a8", "fg": "#1a1a1a"},
    "out of service":   {"bg": "#E53935", "fg": "#ffffff"},
    "report writing":   {"bg": "#CE93D8", "fg": "#1a1a1a"},
    "returning":        {"bg": "#0288D1", "fg": "#ffffff"},
    "tol":              {"bg": "#1565C0", "fg": "#ffffff"},
    "wheels down":      {"bg": "#0288D1", "fg": "#ffffff"},
    "post incident":    {"bg": "#CE93D8", "fg": "#1a1a1a"},
    "find":             {"bg": "#FB8C00", "fg": "#1a1a1a"},
    "complete":         {"bg": "#2E7D32", "fg": "#ffffff"},
}

RESOURCE_STATUS: Dict[str, Dict[str, str]] = {
    "Pending":        {"bg": "#efe229", "fg": "#000000"},
    "Enroute":        {"bg": "#006ab6", "fg": "#000000"},
    "Checked In":     {"bg": "#00e113", "fg": "#000000"},
    "Assigned":       {"bg": "#581ab4", "fg": "#ffffff"},
    "Available":      {"bg": "#098d00", "fg": "#000000"},
    "Out of Service": {"bg": "#c73221", "fg": "#010101"},
    "Demobilized":    {"bg": "#888888", "fg": "#363636"},
}

TASK_STATUS: Dict[str, Dict[str, str]] = {
    "created":          {"bg": "#90A4AE", "fg": "#1a1a1a"},
    "planned":          {"bg": "#CE93D8", "fg": "#1a1a1a"},
    "assigned":         {"bg": "#FFC107", "fg": "#1a1a1a"},
    "in progress":      {"bg": "#00ACC1", "fg": "#ffffff"},
    "complete":         {"bg": "#2E7D32", "fg": "#ffffff"},
    "cancelled":        {"bg": "#E53935", "fg": "#ffffff"},
}

NARRATIVE_STATUS: Dict[str, Dict[str, str]] = {
    "critical": {"bg": "#f2b8b5", "fg": "#1a1a1a"},
}

TEAM_TYPE_COLORS: Dict[str, str] = {
    "GT":       "#228b22",
    "UDF":      "#ffeb3b",
    "LSAR":     "#228b22",
    "DF":       "#ffeb3b",
    "GT/UAS":   "#00b987",
    "UDF/UAS":  "#ffd54f",
    "UAS":      "#00cec9",
    "AIR":      "#00a8ff",
    "K9":       "#8b0000",
    "UTIL":     "#7a7a7a",
}

# Intel module — subject/assessment/item/lead row tints and entity/priority/
# trend accents. "bg" is a semi-transparent row-tint overlay (ARGB hex);
# "fg" is the solid accent used for legend dots and status text.
INTEL_SUBJECT_STATUS: Dict[str, Dict[str, str]] = {
    "missing":  {"bg": "#78b42828", "fg": "#b42828"},
    "located":  {"bg": "#6428a050", "fg": "#28a050"},
    "deceased": {"bg": "#5a646464", "fg": "#646464"},
}

INTEL_ASSESSMENT_STATUS: Dict[str, Dict[str, str]] = {
    "draft":       {"bg": "#6e1e50b4", "fg": "#1e50b4"},
    "in progress": {"bg": "#641478c8", "fg": "#1478c8"},
    "complete":    {"bg": "#6428a050", "fg": "#28a050"},
    "archived":    {"bg": "#50646464", "fg": "#646464"},
}

INTEL_ITEM_STATUS: Dict[str, Dict[str, str]] = {
    "critical":   {"bg": "#82b42828", "fg": "#b42828"},
    "high":       {"bg": "#6ec87814", "fg": "#c87814"},
    "worsening":  {"bg": "#6eb45014", "fg": "#b45014"},
    "improving":  {"bg": "#6428a050", "fg": "#28a050"},
    "ruled_out":  {"bg": "#50646464", "fg": "#646464"},
}

INTEL_LEAD_STATUS: Dict[str, Dict[str, str]] = {
    "unassigned_high": {"bg": "#82b42828", "fg": "#b42828"},
    "unassigned":      {"bg": "#6eb46414", "fg": "#b46414"},
    "new":             {"bg": "#641e50b4", "fg": "#1e50b4"},
    "assigned":        {"bg": "#5a1464a0", "fg": "#1464a0"},
    "converted":       {"bg": "#6428a050", "fg": "#28a050"},
    "closed":          {"bg": "#4b646464", "fg": "#646464"},
}

# Keyed by Intel log/dashboard entity_type. "fg" doubles as the icon/text
# accent used on activity rows and legends.
INTEL_ENTITY_COLORS: Dict[str, Dict[str, str]] = {
    "subject":     {"bg": "#5ab42828", "fg": "#cf4444"},
    "lead":        {"bg": "#50b48c14", "fg": "#d29922"},
    "item":        {"bg": "#501e64c8", "fg": "#4a9eff"},
    "assessment":  {"bg": "#4628a050", "fg": "#2da44e"},
    "observation": {"bg": "#46148cb4", "fg": "#1ab0d0"},
    "attachment":  {"bg": "#46643cb4", "fg": "#9b6fd4"},
    "report":      {"bg": "#3c646464", "fg": "#8b949e"},
    "form":        {"bg": "#3c507850", "fg": "#6da06d"},
}

# Opaque chip colors for the Intel dashboard's priority badges.
INTEL_PRIORITY_COLORS: Dict[str, Dict[str, str]] = {
    "critical": {"fg": "#cf222e", "bg": "#3d1414"},
    "high":     {"fg": "#d29922", "bg": "#3d2c08"},
    "medium":   {"fg": "#338eda", "bg": "#0d2a42"},
    "low":      {"fg": "#6e7781", "bg": "#1c2128"},
}

# Flat trend accent used by the Intel dashboard's critical-item trend label.
INTEL_TREND_COLORS: Dict[str, str] = {
    "worsening": "#cf4444",
    "improving": "#2da44e",
    "stable":    "#8b949e",
    "unknown":   "#8b949e",
}

# Liaison module — bold, saturated opaque fills for agency-status chips,
# priority badges, and the Reporting Board's ready/not-ready state.
LIAISON_AGENCY_STATUS: Dict[str, Dict[str, str]] = {
    "Not Contacted":     {"bg": "#78909C", "fg": "#1a1a1a"},
    "Contacted":         {"bg": "#1976D2", "fg": "#ffffff"},
    "Awaiting Response": {"bg": "#FB8C00", "fg": "#1a1a1a"},
    "Standby":           {"bg": "#5E35B1", "fg": "#ffffff"},
    "Supporting":        {"bg": "#00897B", "fg": "#ffffff"},
    "Active":            {"bg": "#43A047", "fg": "#ffffff"},
    "Demobilizing":      {"bg": "#8E24AA", "fg": "#ffffff"},
    "Released":          {"bg": "#78716C", "fg": "#ffffff"},
    "Unavailable":       {"bg": "#E53935", "fg": "#ffffff"},
}

LIAISON_PRIORITY: Dict[str, Dict[str, str]] = {
    "Low":      {"bg": "#43A047", "fg": "#ffffff"},
    "Medium":   {"bg": "#1976D2", "fg": "#ffffff"},
    "High":     {"bg": "#FB8C00", "fg": "#1a1a1a"},
    "Critical": {"bg": "#E53935", "fg": "#ffffff"},
}

LIAISON_REPORT_STATE: Dict[str, Dict[str, str]] = {
    "ready":     {"bg": "#2E7D32", "fg": "#ffffff"},
    "not_ready": {"bg": "#FB8C00", "fg": "#1a1a1a"},
}

__all__ = [
    "NAMED_COLORS",
    "PALETTE",
    "SURFACE",
    "RESOURCE_STATUS",
    "TEAM_STATUS",
    "TASK_STATUS",
    "NARRATIVE_STATUS",
    "TEAM_TYPE_COLORS",
    "INTEL_SUBJECT_STATUS",
    "INTEL_ASSESSMENT_STATUS",
    "INTEL_ITEM_STATUS",
    "INTEL_LEAD_STATUS",
    "INTEL_ENTITY_COLORS",
    "INTEL_PRIORITY_COLORS",
    "INTEL_TREND_COLORS",
    "LIAISON_AGENCY_STATUS",
    "LIAISON_PRIORITY",
    "LIAISON_REPORT_STATE",
]
