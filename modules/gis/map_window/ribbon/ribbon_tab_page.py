"""RibbonTabPage: lays out RibbonGroups in a single row, left to right —
never wrapping groups onto multiple rows and never scrolling. Each group
wraps its own buttons onto extra rows first (see RibbonGroup); only when a
group still doesn't fit the row at all does it collapse to a small
dropdown button (RibbonGroup.set_collapsed), which reveals the same
buttons in a popup. The same layout rule applies uniformly on every tab.
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QWidget

from modules.gis.map_window.ribbon.ribbon_group import RibbonGroup

_GROUP_SPACING = 0


class RibbonTabPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._groups: list[RibbonGroup] = []
        self._in_relayout = False

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(_GROUP_SPACING)

    def add_group(self, group: RibbonGroup) -> None:
        self._groups.append(group)
        # Freeze the group's "fully expanded" footprint now, while it's
        # still expanded (the default state) — see RibbonGroup docstring
        # for why this must not be recomputed later.
        group.expanded_target_size()
        self._layout.addWidget(group)
        self._relayout()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._relayout()

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt override
        if not self._groups:
            return 0
        return max(g.expanded_target_size().height() for g in self._groups)

    # ------------------------------------------------------------------
    def _relayout(self) -> None:
        if self._in_relayout or not self._groups:
            return
        self._in_relayout = True
        try:
            available = self.width()
            total = sum(g.expanded_target_size().width() for g in self._groups)
            total += _GROUP_SPACING * (len(self._groups) - 1)

            if total <= available:
                for group in self._groups:
                    group.set_collapsed(False)
                return

            # Collapse groups right-to-left until what's left fits. Earlier
            # (left-most) groups are treated as higher priority and stay
            # expanded longest.
            collapsed_ids: set[int] = set()
            for group in reversed(self._groups):
                if total <= available:
                    break
                total -= group.expanded_target_size().width()
                total += group.collapsed_target_width()
                collapsed_ids.add(id(group))

            for group in self._groups:
                group.set_collapsed(id(group) in collapsed_ids)
        finally:
            self._in_relayout = False
