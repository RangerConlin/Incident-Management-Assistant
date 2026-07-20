"""RibbonGroup: a labeled cluster of tool buttons/dropdowns within a ribbon
tab.

A group's buttons wrap onto additional rows (via FlowLayout) once they
exceed a fixed target width, instead of stretching the group arbitrarily
wide. If a group still doesn't fit the tab's single row at all (see
RibbonTabPage), it collapses to one small dropdown button that reveals the
same buttons in a popup — the group is never simply hidden or scrolled.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QLabel,
    QMenu,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from modules.gis.map_window.ribbon.flow_layout import FlowLayout
from utils.styles import ribbon_colors, subscribe_theme

_DEFAULT_MAX_CONTENT_WIDTH = 230
_LARGE_ICON_FONT_PX = 20


def _button_min_size(button: QToolButton, text: str, *, large: bool) -> QSize:
    """Size a button to fully fit its own label, with minimal padding —
    never smaller than the content needs, never padded out beyond it.

    A blanket pixel floor (e.g. "every button is at least 64px wide")
    forces long labels like "Communications Site" to be squeezed and
    mid-word-ellipsized. Measuring each button's own text means it never
    truncates; the group as a whole is what wraps/collapses.
    """
    text_width = button.fontMetrics().horizontalAdvance(text)
    if large:
        return QSize(max(40, text_width + 10), 40)
    return QSize(text_width + 20, 22)


class RibbonGroup(QFrame):
    """A titled group of controls (buttons/dropdowns) inside a ribbon tab page."""

    def __init__(
        self,
        title: str,
        parent: QWidget | None = None,
        *,
        max_content_width: int = _DEFAULT_MAX_CONTENT_WIDTH,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ribbonGroup")
        self._title = title
        self._max_content_width = max_content_width
        self._collapsed = False
        self._expanded_size: QSize | None = None
        self._popup: QWidget | None = None
        self._popup_layout: QVBoxLayout | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 4, 6, 2)
        outer.setSpacing(2)
        self._outer = outer

        # Buttons wrap onto extra rows once they exceed max_content_width —
        # capping this widget's width (not the FlowLayout itself) is what
        # makes Qt's real layout pass wrap at that point.
        self._content = QWidget(self)
        self._content.setMaximumWidth(max_content_width)
        self._buttons_row = FlowLayout(self._content, margin=0, spacing=4)
        outer.addWidget(self._content)

        self._label = QLabel(title, self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        outer.addWidget(self._label)

        # A full title would barely be narrower than the group itself,
        # defeating the point of collapsing — show just its first word
        # (the full name is still in the tooltip).
        short_title = title.split(" ")[0][:10]
        self._collapse_button = QToolButton(self)
        self._collapse_button.setObjectName("ribbonGroupCollapsed")
        self._collapse_button.setText(f"{short_title} ▾")
        self._collapse_button.setToolTip(f"Show {title} options")
        self._collapse_button.setAutoRaise(True)
        self._collapse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._collapse_button.clicked.connect(self._show_popup)
        self._collapse_button.hide()
        outer.addWidget(self._collapse_button)

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        subscribe_theme(self, self._on_theme_changed)

    # ------------------------------------------------------------------
    def add_button(
        self,
        text: str,
        *,
        icon_text: str = "",
        checkable: bool = False,
        tooltip: str = "",
        on_click: Callable[[], None] | None = None,
        large: bool = True,
    ) -> QToolButton:
        button = QToolButton(self._content)
        button.setText(icon_text or text)
        button.setToolTip(tooltip or text)
        button.setCheckable(checkable)
        button.setAutoRaise(True)
        if large:
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            if icon_text:
                button.setObjectName("ribbonIconButton")
        else:
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setMinimumSize(_button_min_size(button, icon_text or text, large=large))
        button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        if on_click is not None:
            button.clicked.connect(on_click)
        self._buttons_row.addWidget(button)
        return button

    def add_menu_button(
        self,
        text: str,
        menu: QMenu,
        *,
        tooltip: str = "",
        large: bool = True,
    ) -> QToolButton:
        button = QToolButton(self._content)
        button.setText(text)
        button.setToolTip(tooltip or text)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setMenu(menu)
        button.setAutoRaise(True)
        if large:
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        else:
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        # Menu buttons also need room for the drop-down arrow indicator.
        min_size = _button_min_size(button, text, large=large)
        min_size.setWidth(min_size.width() + 14)
        button.setMinimumSize(min_size)
        button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._buttons_row.addWidget(button)
        return button

    def add_combo(self, items: list[tuple[str, object]], *, tooltip: str = "") -> QComboBox:
        combo = QComboBox(self._content)
        for label, data in items:
            combo.addItem(label, data)
        if tooltip:
            combo.setToolTip(tooltip)
        combo.setMinimumWidth(80)
        combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._buttons_row.addWidget(combo)
        return combo

    def add_widget(self, widget: QWidget) -> None:
        widget.setParent(self._content)
        self._buttons_row.addWidget(widget)

    def add_stretch(self) -> None:
        pass  # no-op: a FlowLayout has no concept of trailing stretch

    def add_vertical_separator(self) -> None:
        pass  # no-op: rows already wrap; a rule mid-flow reads as clutter

    # -- Collapse / expand ------------------------------------------------
    def expanded_target_size(self) -> QSize:
        """The group's footprint when fully expanded and wrapped at its
        width cap — constant regardless of window size, since the cap is
        fixed. Used by RibbonTabPage to decide, once per resize, which
        groups fit in the row and which must collapse. Computed once and
        cached: recomputing while the group happens to be collapsed (its
        buttons currently living in the popup) would measure the wrong
        thing."""
        if self._expanded_size is None:
            self._expanded_size = self._compute_expanded_size()
        return self._expanded_size

    def _compute_expanded_size(self) -> QSize:
        count = self._buttons_row.count()
        if count == 0:
            content_width = 0
        else:
            spacing = self._buttons_row.spacing()
            natural_width = sum(
                self._buttons_row.itemAt(i).widget().sizeHint().width() for i in range(count)
            )
            natural_width += spacing * (count - 1)
            content_width = min(self._max_content_width, natural_width)
        content_height = self._buttons_row.heightForWidth(content_width) if content_width else 0

        margins = self._outer.contentsMargins()
        label_height = self._label.sizeHint().height()
        collapsed_width = self._collapse_button.sizeHint().width()
        width = max(content_width, collapsed_width) + margins.left() + margins.right()
        height = (
            content_height
            + self._outer.spacing()
            + label_height
            + margins.top()
            + margins.bottom()
        )
        return QSize(width, height)

    def set_collapsed(self, collapsed: bool) -> None:
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        if collapsed:
            self._content.hide()
            self._label.hide()
            self._collapse_button.show()
            if self._popup is not None and self._popup.isVisible():
                self._popup.hide()
        else:
            if self._popup is not None:
                self._popup.hide()
            if self._content.parent() is not self:
                self._content.setParent(self)
                self._outer.insertWidget(0, self._content)
            self._content.show()
            self._label.show()
            self._collapse_button.hide()

    def is_collapsed(self) -> bool:
        return self._collapsed

    def collapsed_target_width(self) -> int:
        return self._collapse_button.sizeHint().width()

    def _show_popup(self) -> None:
        if self._popup is None:
            self._popup = QWidget(self, Qt.WindowType.Popup)
            self._popup_layout = QVBoxLayout(self._popup)
            self._popup_layout.setContentsMargins(6, 6, 6, 6)
            self._popup_layout.setSpacing(2)
        if self._content.parent() is not self._popup:
            self._content.setParent(self._popup)
            self._content.setMaximumWidth(16777215)
            self._popup_layout.addWidget(self._content)
        self._content.show()
        pos = self._collapse_button.mapToGlobal(self._collapse_button.rect().bottomLeft())
        self._popup.move(pos)
        self._popup.show()
        self._popup.adjustSize()

    # ------------------------------------------------------------------
    def _on_theme_changed(self, _name: str) -> None:
        colors = ribbon_colors()
        group_bg = colors["group_bg"]
        group_border = colors["group_border"]
        label_fg = colors["group_label_fg"]
        self.setStyleSheet(
            "QFrame#ribbonGroup {"
            f" background-color: {group_bg.name()};"
            f" border-right: 1px solid {group_border.name()};"
            "}"
            "QToolButton#ribbonIconButton {"
            f" font-size: {_LARGE_ICON_FONT_PX}px;"
            "}"
            "QToolButton#ribbonGroupCollapsed {"
            f" color: {label_fg.name()};"
            f" background-color: {group_bg.name()};"
            f" border: 1px solid {group_border.name()};"
            " border-radius: 3px; padding: 4px 8px;"
            "}"
        )
        self._label.setStyleSheet(f"color: {label_fg.name()}; font-size: 10px;")
