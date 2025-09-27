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
    "menu_bar_bg":  "#1313AB",
    "bg_raised":    "#1B1F2A",
    "fg_primary":   "#ECEFF4",
    "fg_muted":     "#A4ADBA",
    "dock_tab_bg":  "#AF0909",

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
    "btn_bg":       "#E9E9E9",
    "btn_border":   "#D5D8DE",
    "btn_hover":    "#858585",
    "btn_focus":    "#2F80ED",
    "btn_disabled": "#000000",
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
    "enroute":          {"bg": "#a88f1a", "fg": "#f5f5f5"},
    "out of service":   {"bg": "#8c2f2f", "fg": "#f5f5f5"},
    "report writing":   {"bg": "#785b8f", "fg": "#f5f5f5"},
    "returning":        {"bg": "#1f6088", "fg": "#f5f5f5"},
    "tol":              {"bg": "#0b3d75", "fg": "#f5f5f5"},
    "wheels down":      {"bg": "#1f6088", "fg": "#f5f5f5"},
    "post incident":    {"bg": "#785b8f", "fg": "#f5f5f5"},
    "find":             {"bg": "#b2700d", "fg": "#f5f5f5"},
    "complete":         {"bg": "#2f6d34", "fg": "#f5f5f5"},
}

TASK_STATUS: Dict[str, Dict[str, str]] = {
    "created":          {"bg": "#444c55", "fg": "#f5f5f5"},
    "planned":          {"bg": "#6d5478", "fg": "#f5f5f5"},
    "assigned":         {"bg": "#a88f1a", "fg": "#f5f5f5"},
    "in progress":      {"bg": "#1f6088", "fg": "#f5f5f5"},
    "complete":         {"bg": "#2f6d34", "fg": "#f5f5f5"},
    "cancelled":        {"bg": "#8c2f2f", "fg": "#f5f5f5"},
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

__all__ = [
    "NAMED_COLORS",
    "PALETTE",
    "SURFACE",
    "TEAM_STATUS",
    "TASK_STATUS",
    "TEAM_TYPE_COLORS",
]