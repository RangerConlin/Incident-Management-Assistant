# styles/palette.py
# Unified semantic palette for SARApp. Fill hex values with the official palette.
# NOTE: Keep names stable; UI references these tokens.

LIGHT = {
    # Base surface/foreground
    "bg_window": "#FFFFFF",       # TODO: insert official
    "bg_panel":  "#F7F7F8",       # "
    "bg_raised": "#FFFFFF",       # "
    "fg_primary": "#0F0F0F",      # "
    "fg_muted":   "#5A5F6A",      # "

    # Brand & accents
    "accent":    "#2F80ED",       # " brand primary
    "accent_alt":"#27AE60",       # " brand success
    "warning":   "#E2B93B",       # "
    "danger":    "#D64545",       # "
    "info":      "#338EDA",       # "

    # Controls
    "ctrl_bg":   "#FFFFFF",
    "ctrl_border":"#D5D8DE",
    "ctrl_hover":"#EEF2F7",
    "ctrl_focus":"#2F80ED",
    "divider":   "#E7E9EE",
}

DARK = {
    "bg_window": "#0F1115",
    "bg_panel":  "#151821",
    "bg_raised": "#1B1F2A",
    "fg_primary": "#ECEFF4",
    "fg_muted":   "#A4ADBA",

    "accent":    "#5CA3FF",
    "accent_alt":"#4CC38A",
    "warning":   "#E5C558",
    "danger":    "#E5484D",
    "info":      "#5EB0EF",

    "ctrl_bg":   "#1B1F2A",
    "ctrl_border":"#2A2F3A",
    "ctrl_hover":"#212737",
    "ctrl_focus":"#5CA3FF",
    "divider":   "#242A36",
}

# Team Status colors (rows are styled by status). Keep text contrast baked in.
TEAM_STATUS = {
    # Example keys — replace hex values with official ones.
    "AVAILABLE": {"bg": "#E8F5E9", "fg": "#0E5223"},
    "ASSIGNED":  {"bg": "#E3F2FD", "fg": "#0B3A75"},
    "OUT_OF_SERVICE": {"bg": "#FDECEA", "fg": "#7A1E1E"},
    "PENDING":   {"bg": "#FFF8E1", "fg": "#6A4B00"},
}

# Task Status colors
TASK_STATUS = {
    "NEW":       {"bg": "#EEF2FF", "fg": "#1E2A78"},
    "ACTIVE":    {"bg": "#E6F4EA", "fg": "#0E5223"},
    "BLOCKED":   {"bg": "#FFF1F0", "fg": "#7A1E1E"},
    "DONE":      {"bg": "#F1F5F9", "fg": "#1F2937"},
}

THEMES = {"light": LIGHT, "dark": DARK}

