"""RibbonTabPage: wraps RibbonGroups so commands remain visible."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from modules.gis.map_window.ribbon.flow_layout import FlowLayout
from modules.gis.map_window.ribbon.ribbon_group import RibbonGroup

_GROUP_SPACING = 2


class RibbonTabPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._groups: list[RibbonGroup] = []

        self._layout = FlowLayout(self, margin=0, spacing=_GROUP_SPACING)
        self._layout.setSpacing(_GROUP_SPACING)

    def add_group(self, group: RibbonGroup) -> None:
        self._groups.append(group)
        group.expanded_target_size()
        group.set_collapsed(False)
        self._layout.addWidget(group)

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt override
        if not self._groups:
            return 0
        return self._layout.heightForWidth(width)
