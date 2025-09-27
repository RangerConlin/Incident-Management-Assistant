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
    "bg_window":    "#d1d1d1",
    "bg_panel":     "#9E9E9E",
    "menu_bar_bg":  "#1313AB",
    "bg_raised":    "#686868",
    "fg_primary":   "#0F0F0F",
    "fg_muted":     "#5A5F6A",
    "dock_tab_bg":  "#C0C0C0",

    # Additional semantic accents used by reports and specialty panels.
    "accent_alt":   "#27AE60",
    "danger":       "#D64545",
    "info":         "#338EDA",

    # Control states for button chrome, hover rings, focus outlines, and dividers.
    "ctrl_bg":      "#E9E9E9",
    "ctrl_border":  "#D5D8DE",
    "ctrl_hover":   "#858585",
    "ctrl_focus":   "#2F80ED",
    "divider":      "#000000",

    # Buttons
    "btn_bg":       "#E9E9E9",
    "btn_border":   "#D5D8DE",
    "btn_hover":    "#858585",
    "btn_focus":    "#2F80ED",
    "btn_disabled": "#000000",
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
    "aol":              {"bg": "#085ec7", "fg": "#e0e0e0"},
    "arrival":          {"bg": "#17c4eb", "fg": "#333333"},
    "assigned":         {"bg": "#ffeb3b", "fg": "#333333"},
    "available":        {"bg": "#388e3c", "fg": "#ffffff"},
    "break":            {"bg": "#9c27b0", "fg": "#333333"},
    "briefed":          {"bg": "#ffeb3b", "fg": "#333333"},
    "crew rest":        {"bg": "#9c27b0", "fg": "#333333"},
    "enroute":          {"bg": "#ffeb3b", "fg": "#333333"},
    "out of service":   {"bg": "#d32f2f", "fg": "#333333"},
    "report writing":   {"bg": "#ce93d8", "fg": "#333333"},
    "returning":        {"bg": "#0288d1", "fg": "#e1e1e1"},
    "tol":              {"bg": "#085ec7", "fg": "#e0e0e0"},
    "wheels down":      {"bg": "#0288d1", "fg": "#e1e1e1"},
    "post incident":    {"bg": "#ce93d8", "fg": "#333333"},
    "find":             {"bg": "#ffa000", "fg": "#333333"},
    "complete":         {"bg": "#386a3c", "fg": "#333333"},
}

TASK_STATUS: Dict[str, Dict[str, str]] = {
    "created":          {"bg": "#6e7b8b", "fg": "#333333"},
    "planned":          {"bg": "#ce93d8", "fg": "#333333"},
    "assigned":         {"bg": "#ffeb3b", "fg": "#333333"},
    "in progress":      {"bg": "#17c4e8", "fg": "#333333"},
    "complete":         {"bg": "#386a3c", "fg": "#333333"},
    "cancelled":        {"bg": "#d32f2f", "fg": "#333333"},
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

__all__ = [
    "NAMED_COLORS",
    "PALETTE",
    "SURFACE",
    "TEAM_STATUS",
    "TASK_STATUS",
    "TEAM_TYPE_COLORS",
]

