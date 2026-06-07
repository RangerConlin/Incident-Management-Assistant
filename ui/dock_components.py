"""Custom ADS dock components that replace the gradient-painted tab with a flat one."""
from __future__ import annotations

from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QStyle, QStyleOption
from PySide6QtAds import CDockComponentsFactory, CDockWidgetTab


class FlatDockWidgetTab(CDockWidgetTab):
    """CDockWidgetTab that draws a flat background instead of the built-in C++ gradient."""

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)


class FlatDockComponentsFactory(CDockComponentsFactory):
    """Factory that swaps in FlatDockWidgetTab for every dock tab ADS creates."""

    def createDockWidgetTab(self, dock_widget):
        return FlatDockWidgetTab(dock_widget)
