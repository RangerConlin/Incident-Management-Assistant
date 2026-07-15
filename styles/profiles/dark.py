from __future__ import annotations
from typing import Dict

NAMED_COLORS: Dict[str, str] = {
    # Core hyperlink and focus colour tuned for dark backgrounds.
    "PRIMARY_BLUE":  "#58a6ff",
    # Shared accent orange for complementary highlights.
    "ACCENT_ORANGE": "#d29922",
    # Muted descriptive text for labels or placeholder copy.
    "MUTED_TEXT":    "#8b949e",
    # Positive confirmation and health indicators.
    "SUCCESS_GREEN": "#3fb950",
    # Alert tone for risky operations that should pop on dark UI.
    "WARNING_RED":   "#f0883e",
    # Soft blue for neutral information and assistive hints.
    "INFO_BLUE":     "#5eb0ef",
    # Strong error colour for blocking states.
    "DANGER_RED":    "#e5484d",
}

PALETTE: Dict[str, str] = {
    # Core surfaces/foregrounds consumed by the Qt palette helpers.
    "bg":           "#2c2c2c",
    "fg":           "#b4b4b4",
    "muted":        "#888888",
    "accent":       "#90caf9",
    "success":      "#4caf50",
    "warning":      "#ffb300",
    "error":        "#ef5350",

    # Semantic window surfaces used by the legacy styling helpers.
    "bg_window":    "#0F1115",
    "bg_panel":     "#151821",
    "menu_bar_bg":  "#1C2130",
    "bg_raised":    "#1B1F2A",
    "fg_primary":   "#ECEFF4",
    "fg_muted":     "#A4ADBA",
    "dock_tab_bg":  "#1A1E2B",

    # Secondary accent and message tones for reports and charts.
    "accent_alt":   "#4CC38A",
    "danger":       "#E5484D",
    "info":         "#5EB0EF",

    # Control chrome states for hover/focus feedback and separators.
    "ctrl_bg":      "#1B1F2A",
    "ctrl_border":  "#2A2F3A",
    "ctrl_hover":   "#212737",
    "ctrl_focus":   "#5CA3FF",
    "divider":      "#242A36",

    # Buttons
    "btn_bg":       "#2A3042",
    "btn_border":   "#3A4358",
    "btn_hover":    "#353D55",
    "btn_focus":    "#2F80ED",
    "btn_disabled": "#1B1F2A",
    "btn_checked":  "#2F80ED",
}

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

TEAM_STATUS: Dict[str, Dict[str, str]] = {
    "aol":              {"bg": "#0b3d75", "fg": "#f5f5f5"},
    "arrival":          {"bg": "#1f6088", "fg": "#f0f0f0"},
    "assigned":         {"bg": "#a88f1a", "fg": "#f5f5f5"},
    "available":        {"bg": "#2f6d34", "fg": "#f5f5f5"},
    "break":            {"bg": "#6e2b75", "fg": "#f5f5f5"},
    "briefed":          {"bg": "#a88f1a", "fg": "#f5f5f5"},
    "crew rest":        {"bg": "#6e2b75", "fg": "#f5f5f5"},
    "enroute":          {"bg": "#1aa8a8", "fg": "#f5f5f5"},
    "out of service":   {"bg": "#8c2f2f", "fg": "#f5f5f5"},
    "report writing":   {"bg": "#785b8f", "fg": "#f5f5f5"},
    "returning":        {"bg": "#1f6088", "fg": "#f5f5f5"},
    "tol":              {"bg": "#0b3d75", "fg": "#f5f5f5"},
    "wheels down":      {"bg": "#1f6088", "fg": "#f5f5f5"},
    "post incident":    {"bg": "#785b8f", "fg": "#f5f5f5"},
    "find":             {"bg": "#b2700d", "fg": "#f5f5f5"},
    "complete":         {"bg": "#2f6d34", "fg": "#f5f5f5"},
}

RESOURCE_STATUS: Dict[str, Dict[str, str]] = {
    "Pending":        {"bg": "#4e3c00", "fg": "#dbdbdb"},
    "Enroute":        {"bg": "#0d2a4a", "fg": "#dbdbdb"},
    "Checked In":     {"bg": "#1b3a1f", "fg": "#dbdbdb"},
    "Assigned":       {"bg": "#2a1a4e", "fg": "#dbdbdb"},
    "Available":      {"bg": "#003636", "fg": "#dbdbdb"},
    "Out of Service": {"bg": "#4a1200", "fg": "#dbdbdb"},
    "Demobilized":    {"bg": "#1c2226", "fg": "#dbdbdb"},
}

TASK_STATUS: Dict[str, Dict[str, str]] = {
    "created":          {"bg": "#444c55", "fg": "#f5f5f5"},
    "planned":          {"bg": "#6d5478", "fg": "#f5f5f5"},
    "assigned":         {"bg": "#a88f1a", "fg": "#f5f5f5"},
    "in progress":      {"bg": "#1f6088", "fg": "#f5f5f5"},
    "complete":         {"bg": "#2f6d34", "fg": "#f5f5f5"},
    "cancelled":        {"bg": "#8c2f2f", "fg": "#f5f5f5"},
}

NARRATIVE_STATUS: Dict[str, Dict[str, str]] = {
    "critical": {"bg": "#5c1a1a", "fg": "#f5f5f5"},
}

TEAM_TYPE_COLORS: Dict[str, str] = {
    "GT":       "#2f6d34",
    "UDF":      "#bfa523",
    "LSAR":     "#2f6d34",
    "DF":       "#bfa523",
    "GT/UAS":   "#2d8f6d",
    "UDF/UAS":  "#c59b3f",
    "UAS":      "#1f7a83",
    "AIR":      "#3583c4",
    "K9":       "#a03a3a",
    "UTIL":     "#5a5a5a",
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
    "Not Contacted":     {"bg": "#52525b", "fg": "#f5f5f5"},
    "Contacted":         {"bg": "#1d4ed8", "fg": "#ffffff"},
    "Awaiting Response": {"bg": "#b45309", "fg": "#ffffff"},
    "Standby":           {"bg": "#4338ca", "fg": "#ffffff"},
    "Supporting":        {"bg": "#0f766e", "fg": "#ffffff"},
    "Active":            {"bg": "#15803d", "fg": "#ffffff"},
    "Demobilizing":      {"bg": "#7e22ce", "fg": "#ffffff"},
    "Released":          {"bg": "#3f3f46", "fg": "#f5f5f5"},
    "Unavailable":       {"bg": "#b91c1c", "fg": "#ffffff"},
}

LIAISON_PRIORITY: Dict[str, Dict[str, str]] = {
    "Low":      {"bg": "#15803d", "fg": "#ffffff"},
    "Medium":   {"bg": "#1d4ed8", "fg": "#ffffff"},
    "High":     {"bg": "#c2410c", "fg": "#ffffff"},
    "Critical": {"bg": "#b91c1c", "fg": "#ffffff"},
}

LIAISON_REPORT_STATE: Dict[str, Dict[str, str]] = {
    "ready":     {"bg": "#16a34a", "fg": "#ffffff"},
    "not_ready": {"bg": "#b45309", "fg": "#ffffff"},
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
