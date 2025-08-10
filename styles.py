from PySide6.QtGui import QColor, QBrush, QFont

# -----------------------------
# Task Status Colors
# -----------------------------
TASK_STATUS_COLORS = {
    "created":     {"bg": QBrush(QColor("#6e7b8b")), "fg": QBrush(QColor("#333333"))},
    "planned":     {"bg": QBrush(QColor("#ce93d8")), "fg": QBrush(QColor("#333333"))},
    "assigned":    {"bg": QBrush(QColor("#ffeb3b")), "fg": QBrush(QColor("#333333"))},
    "in progress": {"bg": QBrush(QColor("#17c4e8")), "fg": QBrush(QColor("#333333"))},
    "complete":    {"bg": QBrush(QColor("#386a3c")), "fg": QBrush(QColor("#333333"))},
    "cancelled":   {"bg": QBrush(QColor("#d32f2f")), "fg": QBrush(QColor("#333333"))},
}

# -----------------------------
# Team Status Colors
# -----------------------------
TEAM_STATUS_COLORS = {
    "aol":            {"bg": QBrush(QColor("#085ec7")), "fg": QBrush(QColor("#e0e0e0"))},
    "arrival":        {"bg": QBrush(QColor("#17c4eb")), "fg": QBrush(QColor("#333333"))},
    "assigned":       {"bg": QBrush(QColor("#ffeb3b")), "fg": QBrush(QColor("#333333"))},
    "available":      {"bg": QBrush(QColor("#388e3c")), "fg": QBrush(QColor("#ffffff"))},
    "break":          {"bg": QBrush(QColor("#9c27b0")), "fg": QBrush(QColor("#333333"))},
    "briefed":        {"bg": QBrush(QColor("#ffeb3b")), "fg": QBrush(QColor("#333333"))},
    "crew rest":      {"bg": QBrush(QColor("#9c27b0")), "fg": QBrush(QColor("#333333"))},
    "enroute":        {"bg": QBrush(QColor("#ffeb3b")), "fg": QBrush(QColor("#333333"))},
    "out of service": {"bg": QBrush(QColor("#d32f2f")), "fg": QBrush(QColor("#333333"))},
    "report writing": {"bg": QBrush(QColor("#ce93d8")), "fg": QBrush(QColor("#333333"))},
    "returning":      {"bg": QBrush(QColor("#0288d1")), "fg": QBrush(QColor("#e1e1e1"))},
    "tol":            {"bg": QBrush(QColor("#085ec7")), "fg": QBrush(QColor("#e0e0e0"))},
    "wheels down":    {"bg": QBrush(QColor("#0288d1")), "fg": QBrush(QColor("#e1e1e1"))},
    "post mission":   {"bg": QBrush(QColor("#ce93d8")), "fg": QBrush(QColor("#333333"))},
    "find":           {"bg": QBrush(QColor("#ffa000")), "fg": QBrush(QColor("#333333"))},
    "complete":       {"bg": QBrush(QColor("#386a3c")), "fg": QBrush(QColor("#333333"))},
    }

# -----------------------------
# Team Type Colors
# -----------------------------
TEAM_TYPE_COLORS = {
    "GT":      QColor("#228b22"),
    "UDF":     QColor("#ffeb3b"),
    "LSAR":    QColor("228b22"),
    "DF":      QColor("ffeb3b"),
    "GT/UAS":  QColor("00b987"),
    "UDF/UAS": QColor("ffd54f"),
    "UAS":     QColor("#00cec9"),
    "AIR":     QColor("#00a8ff"),
    "K9":      QColor("#8b0000"),
    "UTIL":    QColor("gray"),
}

# -----------------------------
# Light Mode UI Colors
# -----------------------------
LIGHT_MODE = {
    "background": QColor("#f5f5f5"),
    "text":       QColor("#000000"),
    "primary":    QColor("#003a67"),
    "secondary":  QColor("#e0e0e0"),
    "highlight":  QColor("#ffd54f")
}

# -----------------------------
# Dark Mode UI Colors
# -----------------------------
DARK_MODE = {
    "background": QColor("#2c2c2c"),
    "text":       QColor("#ffffff"),
    "primary":    QColor("#003a67"),
    "secondary":  QColor("#424242"),
    "highlight":  QColor("#ffb300")
}
# ─────────────────────────────
# EXAMPLE GLOBAL STYLES
# ─────────────────────────────
STYLE_CARD = """
    background-color: #ffffff;
    border: 1px solid #ccc;
    border-radius: 6px;
    padding: 8px;
"""

STYLE_HEADER = """
    font-weight: bold;
    font-size: 14px;
    color: #003a67;
"""
# ─────────────────────────────
# FONTS
# ─────────────────────────────
FONT_DEFAULT = QFont("Segoe UI", 10)
FONT_TITLE =   QFont("Segoe UI", 12, QFont.Bold)
FONT_SMALL =   QFont("Segoe UI", 8)
