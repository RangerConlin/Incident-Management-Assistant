"""RibbonWidget: Office-style tab bar + collapsible group content area.

States:
- expanded (pinned): tab row + content area always visible.
- collapsed: only the tab row is visible; content area is hidden.
- temporary expand: while collapsed, clicking a tab reveals its content
  area until the user clicks outside the ribbon, at which point it
  collapses again.
- double-clicking a tab toggles the pinned/collapsed state.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QStackedWidget,
    QTabBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from utils.styles import ribbon_colors, subscribe_theme

_MIN_CONTENT_HEIGHT = 74


class RibbonWidget(QFrame):
    """Top-docked ribbon: QTabBar + a QStackedWidget of RibbonGroup rows."""

    collapsedChanged = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ribbonWidget")
        self._pages: dict[str, QWidget] = {}
        self._page_order: list[str] = []
        self._pinned = True
        self._temporary_expanded = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(4, 0, 4, 0)
        top_row.setSpacing(0)

        self._tab_bar = QTabBar(self)
        self._tab_bar.setExpanding(False)
        self._tab_bar.setDrawBase(False)
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        top_row.addWidget(self._tab_bar, 1)

        self._collapse_button = QToolButton(self)
        self._collapse_button.setObjectName("ribbonCollapseButton")
        self._collapse_button.setCheckable(True)
        self._collapse_button.setAutoRaise(True)
        self._collapse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._collapse_button.setMinimumSize(28, 22)
        self._collapse_button.clicked.connect(self._toggle_pinned)
        top_row.addWidget(self._collapse_button)

        outer.addLayout(top_row)

        # Each tab page lays its groups out with a FlowLayout: as the window
        # narrows, groups wrap onto additional rows instead of being hidden,
        # scrolled, or squeezed into illegible text. The stack's own height
        # is therefore not fixed — it's recomputed from the current page's
        # heightForWidth() whenever the width or active tab changes.
        self._content_area = QStackedWidget(self)
        self._content_area.setFixedHeight(_MIN_CONTENT_HEIGHT)
        self._content_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        outer.addWidget(self._content_area)

        subscribe_theme(self, self._on_theme_changed)
        QApplication.instance().installEventFilter(self) if QApplication.instance() else None
        self._apply_visibility()

    # ------------------------------------------------------------------
    def add_tab(self, key: str, title: str, page: QWidget) -> None:
        self._pages[key] = page
        self._page_order.append(key)
        self._content_area.addWidget(page)
        self._tab_bar.addTab(title)
        if self._tab_bar.count() == 1:
            self._tab_bar.setCurrentIndex(0)
            self._content_area.setCurrentWidget(page)

    def set_current_tab(self, key: str) -> None:
        if key not in self._pages:
            return
        idx = self._page_order.index(key)
        self._tab_bar.setCurrentIndex(idx)

    def current_tab_key(self) -> str | None:
        idx = self._tab_bar.currentIndex()
        if 0 <= idx < len(self._page_order):
            return self._page_order[idx]
        return None

    # ------------------------------------------------------------------
    def is_collapsed(self) -> bool:
        return not self._pinned and not self._temporary_expanded

    def _toggle_pinned(self) -> None:
        self._pinned = not self._pinned
        self._temporary_expanded = False
        self._apply_visibility()

    def set_pinned(self, pinned: bool) -> None:
        self._pinned = pinned
        self._temporary_expanded = False
        self._apply_visibility()

    def _on_tab_changed(self, index: int) -> None:
        if 0 <= index < len(self._page_order):
            key = self._page_order[index]
            page = self._pages[key]
            self._content_area.setCurrentWidget(page)
            self._update_content_height()
        if not self._pinned:
            self._temporary_expanded = True
            self._apply_visibility()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._update_content_height()

    def _update_content_height(self) -> None:
        page = self._content_area.currentWidget()
        if page is None:
            return
        width = self._content_area.width()
        if width <= 0:
            return
        height = max(_MIN_CONTENT_HEIGHT, page.heightForWidth(width))
        if self._pinned or self._temporary_expanded:
            self._content_area.setFixedHeight(height)

    def _apply_visibility(self) -> None:
        visible = self._pinned or self._temporary_expanded
        self._content_area.setVisible(visible)
        if visible:
            self._update_content_height()
        else:
            self._content_area.setFixedHeight(0)
        self._collapse_button.setChecked(not self._pinned)
        if self._pinned:
            self._collapse_button.setText("▲")
            self._collapse_button.setToolTip("Collapse the ribbon (double-click a tab does the same)")
        else:
            self._collapse_button.setText("▼")
            self._collapse_button.setToolTip("Pin the ribbon open")
        self.collapsedChanged.emit(self.is_collapsed())

    # ------------------------------------------------------------------
    def eventFilter(self, watched: QWidget, event: QEvent) -> bool:  # noqa: N802 - Qt override
        if (
            event.type() == QEvent.Type.MouseButtonPress
            and self._temporary_expanded
            and not self._pinned
        ):
            # Collapse again if the click landed outside this ribbon widget.
            try:
                global_pos = event.globalPosition().toPoint()  # type: ignore[attr-defined]
                local_pos = self.mapFromGlobal(global_pos)
                if not self.rect().contains(local_pos):
                    self._temporary_expanded = False
                    self._apply_visibility()
            except Exception:
                pass
        return super().eventFilter(watched, event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt override
        tab_rect = self._tab_bar.geometry()
        if tab_rect.contains(event.pos()):
            self._toggle_pinned()
        super().mouseDoubleClickEvent(event)

    # ------------------------------------------------------------------
    def _on_theme_changed(self, _name: str) -> None:
        colors = ribbon_colors()
        tab_bar_bg = colors["tab_bar_bg"]
        active_bg = colors["tab_active_bg"]
        active_fg = colors["tab_active_fg"]
        inactive_fg = colors["tab_inactive_fg"]
        hover_bg = colors["tab_hover_bg"]
        underline = colors["tab_underline"]
        self.setStyleSheet(
            "QFrame#ribbonWidget {"
            f" background-color: {tab_bar_bg.name()};"
            "}"
            "QTabBar::tab {"
            f" color: {inactive_fg.name()};"
            " padding: 4px 12px; margin: 0; border: none;"
            "}"
            "QTabBar::tab:selected {"
            f" color: {active_fg.name()};"
            f" background-color: {active_bg.name()};"
            f" border-bottom: 2px solid {underline.name()};"
            "}"
            "QTabBar::tab:hover {"
            f" background-color: {hover_bg.name()};"
            "}"
            "QToolButton#ribbonCollapseButton {"
            f" color: {inactive_fg.name()};"
            f" background-color: {active_bg.name()};"
            f" border: 1px solid {underline.name()};"
            " border-radius: 3px; margin: 2px;"
            "}"
            "QToolButton#ribbonCollapseButton:hover {"
            f" background-color: {hover_bg.name()};"
            f" color: {active_fg.name()};"
            "}"
            "QToolButton#ribbonCollapseButton:checked {"
            f" background-color: {hover_bg.name()};"
            "}"
        )
