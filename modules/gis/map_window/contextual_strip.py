"""ContextualStrip: thin strip below the ribbon reflecting current selection/tool state.

Shown when a feature is selected or a tool is active; hidden otherwise. Kept
intentionally simple for this milestone — a label plus a small action row —
since the plan defers full contextual-tab chrome.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from modules.gis.models.spatial_feature import SpatialFeature
from utils.styles import ribbon_colors, subscribe_theme


class ContextualStrip(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("contextualStrip")
        self._selected_feature: SpatialFeature | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(8)

        self._label = QLabel("", self)
        layout.addWidget(self._label)
        layout.addStretch(1)

        self._open_details_button = QPushButton("Open Details", self)
        self._edit_vertices_button = QPushButton("Edit Vertices", self)
        self._buffer_button = QPushButton("Add Buffer", self)
        self._delete_button = QPushButton("Delete", self)
        for button in (
            self._open_details_button,
            self._edit_vertices_button,
            self._buffer_button,
            self._delete_button,
        ):
            layout.addWidget(button)

        subscribe_theme(self, self._on_theme_changed)
        self.set_selection(None)

    # ------------------------------------------------------------------
    def set_selection(self, feature: SpatialFeature | None) -> None:
        self._selected_feature = feature
        if feature is None:
            self.setVisible(False)
            return
        self.setVisible(True)
        self._label.setText(f"Selected: {feature.label} ({feature.feature_type.value})")
        editable = not feature.is_locked and feature.source_module == "gis.map_window"
        self._edit_vertices_button.setEnabled(editable)
        self._delete_button.setEnabled(editable)

    def set_active_tool(self, tool_name: str) -> None:
        if self._selected_feature is not None:
            return
        if tool_name in {"pan", "select"}:
            self.setVisible(False)
            return
        self.setVisible(True)
        self._label.setText(f"Tool active: {tool_name.replace('_', ' ').title()} (Esc to cancel)")
        for button in (
            self._open_details_button,
            self._edit_vertices_button,
            self._buffer_button,
            self._delete_button,
        ):
            button.setEnabled(False)

    def connect_open_details(self, slot) -> None:
        self._open_details_button.clicked.connect(slot)

    def connect_edit_vertices(self, slot) -> None:
        self._edit_vertices_button.clicked.connect(slot)

    def connect_buffer(self, slot) -> None:
        self._buffer_button.clicked.connect(slot)

    def connect_delete(self, slot) -> None:
        self._delete_button.clicked.connect(slot)

    # ------------------------------------------------------------------
    def _on_theme_changed(self, _name: str) -> None:
        colors = ribbon_colors()
        bg = colors["strip_bg"]
        border = colors["strip_border"]
        self.setStyleSheet(
            "QFrame#contextualStrip {"
            f" background-color: {bg.name()};"
            f" border-bottom: 1px solid {border.name()};"
            "}"
        )
