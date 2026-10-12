"""StatusChip — a compact, color-coded label pill for displaying status, priority,
confidence, and trend values throughout the Intel Module.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget
from PySide6.QtCore import Qt


# ---------------------------------------------------------------------------
# Color mappings for each value category
# ---------------------------------------------------------------------------

_PRIORITY_COLORS: dict[str, tuple[str, str]] = {
    "Critical": ("#cf222e", "#ffffff"),
    "High":     ("#d29922", "#ffffff"),
    "Medium":   ("#1f6feb", "#ffffff"),
    "Low":      ("#6e7781", "#ffffff"),
}

_STATUS_COLORS: dict[str, tuple[str, str]] = {
    # Subjects
    "Missing":          ("#cf222e", "#ffffff"),
    "Located":          ("#2da44e", "#ffffff"),
    "Deceased":         ("#6e7781", "#ffffff"),
    # Leads
    "New":              ("#1f6feb", "#ffffff"),
    "Assigned":         ("#338eda", "#ffffff"),
    "In Progress":      ("#d29922", "#ffffff"),
    "Follow-Up Complete": ("#2da44e", "#ffffff"),
    "Converted":        ("#6e7781", "#ffffff"),
    "Closed":           ("#6e7781", "#ffffff"),
    "Rejected":         ("#cf222e", "#ffffff"),
    # General
    "Active":           ("#2da44e", "#ffffff"),
    "Monitoring":       ("#338eda", "#ffffff"),
    "Resolved":         ("#6e7781", "#ffffff"),
    "Archived":         ("#6e7781", "#ffffff"),
    # Reports / Assessments
    "Draft":            ("#d29922", "#ffffff"),
    "Published":        ("#2da44e", "#ffffff"),
    "Finalized":        ("#2da44e", "#ffffff"),
}

_TREND_COLORS: dict[str, tuple[str, str]] = {
    "Improving":  ("#2da44e", "#ffffff"),
    "Stable":     ("#1f6feb", "#ffffff"),
    "Worsening":  ("#cf222e", "#ffffff"),
    "Unknown":    ("#6e7781", "#ffffff"),
}

_CONFIDENCE_COLORS: dict[str, tuple[str, str]] = {
    "Confirmed":    ("#2da44e", "#ffffff"),
    "Probable":     ("#1f6feb", "#ffffff"),
    "Possible":     ("#d29922", "#ffffff"),
    "Unconfirmed":  ("#6e7781", "#ffffff"),
}

# Merged lookup — checked in order
_ALL_COLORS: dict[str, tuple[str, str]] = {
    **_PRIORITY_COLORS,
    **_STATUS_COLORS,
    **_TREND_COLORS,
    **_CONFIDENCE_COLORS,
}

_DEFAULT_CHIP = ("#444444", "#ffffff")


class StatusChip(QLabel):
    """A small colored pill label displaying a single status/priority/trend value.

    Usage::

        chip = StatusChip("Critical")
        chip = StatusChip("Worsening", category="trend")
    """

    def __init__(
        self,
        text: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self._apply_style(text)

    def set_value(self, text: str) -> None:
        """Update the chip text and repaint with the corresponding color."""
        self.setText(text)
        self._apply_style(text)

    def _apply_style(self, text: str) -> None:
        bg, fg = _ALL_COLORS.get(text, _DEFAULT_CHIP)
        self.setStyleSheet(f"""
            QLabel {{
                background: {bg};
                color: {fg};
                border-radius: 10px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
        """)
        self.setFixedHeight(22)
