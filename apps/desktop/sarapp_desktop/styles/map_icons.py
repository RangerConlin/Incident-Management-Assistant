"""Procedural pictograph icons for the map window ribbon toolbar.

Follows the drawing conventions in styles/icons.py: each icon is painted
onto a transparent QPixmap using the active palette's foreground color, so
it stays legible in both light and dark themes without hardcoding colors.
"""
from __future__ import annotations

import functools
import math
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from .styles import get_palette
from .tokens import ICON_SIZE_LG

Painter = QPainter
DrawFn = Callable[[Painter, QRectF, QColor], None]


def _make_icon(draw_fn: DrawFn, size: int = ICON_SIZE_LG) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    draw_fn(painter, QRectF(0, 0, size, size), QColor(get_palette()["fg"]))
    painter.end()
    return QIcon(pixmap)


def _pen(color: QColor, width: float = 1.8) -> QPen:
    pen = QPen(color)
    pen.setWidthF(width)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    return pen


def _four_way_arrows(p: Painter, rect: QRectF, color: QColor, arm_ratio: float = 0.36) -> None:
    p.setPen(_pen(color))
    c = rect.center()
    arm = rect.width() * arm_ratio
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        end = QPointF(c.x() + dx * arm, c.y() + dy * arm)
        p.drawLine(c, end)
    p.setBrush(color)
    p.setPen(Qt.PenStyle.NoPen)
    s = rect.width() * 0.1
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        tip = QPointF(c.x() + dx * arm, c.y() + dy * arm)
        path = QPainterPath()
        if dx == 0:
            path.moveTo(tip.x() - s, tip.y() - dy * s)
            path.lineTo(tip.x() + s, tip.y() - dy * s)
            path.lineTo(tip.x(), tip.y() + dy * s * 0.6)
        else:
            path.moveTo(tip.x() - dx * s, tip.y() - s)
            path.lineTo(tip.x() - dx * s, tip.y() + s)
            path.lineTo(tip.x() + dx * s * 0.6, tip.y())
        path.closeSubpath()
        p.drawPath(path)


@functools.lru_cache(maxsize=None)
def icon_pan() -> QIcon:
    return _make_icon(lambda p, r, c: _four_way_arrows(p, r, c))


@functools.lru_cache(maxsize=None)
def icon_move() -> QIcon:
    return _make_icon(lambda p, r, c: _four_way_arrows(p, r, c, arm_ratio=0.3))


@functools.lru_cache(maxsize=None)
def icon_select() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        pen = _pen(color, 1.6)
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(rect.adjusted(4, 4, -4, -4))
    return _make_icon(_draw)


def _magnifier(p: Painter, rect: QRectF, color: QColor, sign: str) -> None:
    p.setPen(_pen(color))
    p.setBrush(Qt.BrushStyle.NoBrush)
    glass = QRectF(rect.left() + 2, rect.top() + 2, rect.width() * 0.6, rect.width() * 0.6)
    p.drawEllipse(glass)
    p.drawLine(glass.bottomRight() - QPointF(2, 2), rect.bottomRight() - QPointF(2, 2))
    center = glass.center()
    half = glass.width() * 0.22
    p.drawLine(QPointF(center.x() - half, center.y()), QPointF(center.x() + half, center.y()))
    if sign == "+":
        p.drawLine(QPointF(center.x(), center.y() - half), QPointF(center.x(), center.y() + half))


@functools.lru_cache(maxsize=None)
def icon_zoom_in() -> QIcon:
    return _make_icon(lambda p, r, c: _magnifier(p, r, c, "+"))


@functools.lru_cache(maxsize=None)
def icon_zoom_out() -> QIcon:
    return _make_icon(lambda p, r, c: _magnifier(p, r, c, "-"))


def _chevron(p: Painter, rect: QRectF, color: QColor, direction: int) -> None:
    p.setPen(_pen(color, 2.2))
    p.setBrush(Qt.BrushStyle.NoBrush)
    c = rect.center()
    w = rect.width() * 0.18
    h = rect.height() * 0.22
    path = QPainterPath()
    path.moveTo(c.x() + direction * w, c.y() - h)
    path.lineTo(c.x() - direction * w, c.y())
    path.lineTo(c.x() + direction * w, c.y() + h)
    p.drawPath(path)


@functools.lru_cache(maxsize=None)
def icon_prev_extent() -> QIcon:
    return _make_icon(lambda p, r, c: _chevron(p, r, c, 1))


@functools.lru_cache(maxsize=None)
def icon_next_extent() -> QIcon:
    return _make_icon(lambda p, r, c: _chevron(p, r, c, -1))


@functools.lru_cache(maxsize=None)
def icon_search() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        p.setPen(_pen(color))
        p.setBrush(Qt.BrushStyle.NoBrush)
        glass = QRectF(rect.left() + 3, rect.top() + 3, rect.width() * 0.62, rect.width() * 0.62)
        p.drawEllipse(glass)
        p.drawLine(glass.bottomRight() - QPointF(2, 2), rect.bottomRight() - QPointF(2, 2))
    return _make_icon(_draw)


@functools.lru_cache(maxsize=None)
def icon_coordinate_entry() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        p.setPen(_pen(color, 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        c = rect.center()
        r_out = rect.width() * 0.4
        r_in = rect.width() * 0.12
        p.drawEllipse(c, r_out, r_out)
        p.drawEllipse(c, r_in, r_in)
        p.drawLine(QPointF(c.x(), rect.top()), QPointF(c.x(), rect.top() + rect.height() * 0.16))
        p.drawLine(QPointF(c.x(), rect.bottom()), QPointF(c.x(), rect.bottom() - rect.height() * 0.16))
        p.drawLine(QPointF(rect.left(), c.y()), QPointF(rect.left() + rect.width() * 0.16, c.y()))
        p.drawLine(QPointF(rect.right(), c.y()), QPointF(rect.right() - rect.width() * 0.16, c.y()))
    return _make_icon(_draw)


@functools.lru_cache(maxsize=None)
def icon_my_location() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        w = rect.width()
        path = QPainterPath()
        path.moveTo(w * 0.5, rect.top() + 1)
        path.cubicTo(w * 0.9, rect.top() + w * 0.35, w * 0.9, rect.top() + w * 0.55, w * 0.5, rect.bottom() - 1)
        path.cubicTo(w * 0.1, rect.top() + w * 0.55, w * 0.1, rect.top() + w * 0.35, w * 0.5, rect.top() + 1)
        p.drawPath(path)
        p.setBrush(get_palette()["bg"])
        p.drawEllipse(QPointF(w * 0.5, rect.top() + w * 0.36), w * 0.13, w * 0.13)
    return _make_icon(_draw)


def _pin(p: Painter, rect: QRectF, color: QColor) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    w = rect.width()
    path = QPainterPath()
    path.moveTo(w * 0.5, rect.top() + 1)
    path.cubicTo(w * 0.9, rect.top() + w * 0.35, w * 0.9, rect.top() + w * 0.55, w * 0.5, rect.bottom() - 1)
    path.cubicTo(w * 0.1, rect.top() + w * 0.55, w * 0.1, rect.top() + w * 0.35, w * 0.5, rect.top() + 1)
    p.drawPath(path)
    p.setBrush(get_palette()["bg"])
    p.drawEllipse(QPointF(w * 0.5, rect.top() + w * 0.36), w * 0.12, w * 0.12)


@functools.lru_cache(maxsize=None)
def icon_marker() -> QIcon:
    return _make_icon(_pin)


@functools.lru_cache(maxsize=None)
def icon_hazard() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        path = QPainterPath()
        path.moveTo(rect.center().x(), rect.top() + 2)
        path.lineTo(rect.right() - 2, rect.bottom() - 2)
        path.lineTo(rect.left() + 2, rect.bottom() - 2)
        path.closeSubpath()
        p.drawPath(path)
        p.setBrush(get_palette()["bg"])
        cx = rect.center().x()
        p.drawRect(QRectF(cx - 1.0, rect.center().y() - 2, 2.0, rect.bottom() - rect.center().y() - 5))
        p.drawEllipse(QPointF(cx, rect.bottom() - 4), 1.4, 1.4)
    return _make_icon(_draw)


@functools.lru_cache(maxsize=None)
def icon_clue() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        p.setPen(_pen(color, 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        glass = QRectF(rect.left() + 2, rect.top() + 2, rect.width() * 0.55, rect.width() * 0.55)
        p.drawEllipse(glass)
        p.drawLine(glass.bottomRight() - QPointF(1, 1), rect.bottomRight() - QPointF(3, 3))
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(glass.center(), glass.width() * 0.12, glass.width() * 0.12)
    return _make_icon(_draw)


@functools.lru_cache(maxsize=None)
def icon_task_area() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        pen = _pen(color, 1.6)
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        fill = QColor(color)
        fill.setAlpha(60)
        p.setBrush(fill)
        inset = rect.adjusted(3, 3, -3, -3)
        path = QPainterPath()
        path.moveTo(inset.left(), inset.top() + inset.height() * 0.3)
        path.lineTo(inset.left() + inset.width() * 0.4, inset.top())
        path.lineTo(inset.right(), inset.top() + inset.height() * 0.25)
        path.lineTo(inset.right() - inset.width() * 0.15, inset.bottom())
        path.lineTo(inset.left() + inset.width() * 0.2, inset.bottom() - inset.height() * 0.1)
        path.closeSubpath()
        p.drawPath(path)
    return _make_icon(_draw)


@functools.lru_cache(maxsize=None)
def icon_measure() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        p.setPen(_pen(color, 1.8))
        inset = rect.adjusted(3, 8, -3, -8)
        p.drawLine(inset.topLeft(), inset.bottomRight())
        # tick marks along the ruler
        length = math.hypot(inset.width(), inset.height())
        steps = 4
        for i in range(1, steps):
            t = i / steps
            x = inset.left() + inset.width() * t
            y = inset.top() + inset.height() * t
            dx = inset.height() / length * 2.2
            dy = inset.width() / length * 2.2
            p.drawLine(QPointF(x - dx, y + dy), QPointF(x + dx, y - dy))
    return _make_icon(_draw)


@functools.lru_cache(maxsize=None)
def icon_extent() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        p.setPen(_pen(color, 1.8))
        inset = rect.adjusted(3, 3, -3, -3)
        arm = inset.width() * 0.3
        for corner, dx, dy in (
            (inset.topLeft(), 1, 0),
            (inset.topRight(), -1, 0),
            (inset.bottomLeft(), 1, 0),
            (inset.bottomRight(), -1, 0),
        ):
            p.drawLine(corner, QPointF(corner.x() + dx * arm, corner.y()))
            vdy = 1 if corner.y() < inset.center().y() else -1
            p.drawLine(corner, QPointF(corner.x(), corner.y() + vdy * arm))
    return _make_icon(_draw)


@functools.lru_cache(maxsize=None)
def icon_clear() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        p.setPen(_pen(color, 2.0))
        inset = rect.adjusted(5, 5, -5, -5)
        p.drawLine(inset.topLeft(), inset.bottomRight())
        p.drawLine(inset.topRight(), inset.bottomLeft())
    return _make_icon(_draw)


@functools.lru_cache(maxsize=None)
def icon_zoom_to_selection() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        p.setPen(_pen(color, 1.8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        c = rect.center()
        r = rect.width() * 0.3
        p.drawEllipse(c, r, r)
        p.drawLine(QPointF(c.x(), rect.top() + 1), QPointF(c.x(), c.y() - r * 0.5))
        p.drawLine(QPointF(c.x(), c.y() + r * 0.5), QPointF(c.x(), rect.bottom() - 1))
        p.drawLine(QPointF(rect.left() + 1, c.y()), QPointF(c.x() - r * 0.5, c.y()))
        p.drawLine(QPointF(c.x() + r * 0.5, c.y()), QPointF(rect.right() - 1, c.y()))
    return _make_icon(_draw)


@functools.lru_cache(maxsize=None)
def icon_draw_point() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawEllipse(rect.center(), rect.width() * 0.14, rect.width() * 0.14)
    return _make_icon(_draw)


@functools.lru_cache(maxsize=None)
def icon_draw_line() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        p.setPen(_pen(color, 2.0))
        p.drawLine(rect.bottomLeft() + QPointF(3, -3), rect.topRight() + QPointF(-3, 3))
    return _make_icon(_draw)


@functools.lru_cache(maxsize=None)
def icon_draw_arc() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        p.setPen(_pen(color, 2.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        inset = rect.adjusted(2, 6, -2, -6)
        p.drawArc(inset, 0, 180 * 16)
    return _make_icon(_draw)


@functools.lru_cache(maxsize=None)
def icon_draw_polygon() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        p.setPen(_pen(color, 1.8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        inset = rect.adjusted(3, 3, -3, -3)
        path = QPainterPath()
        path.moveTo(inset.center().x(), inset.top())
        path.lineTo(inset.right(), inset.top() + inset.height() * 0.38)
        path.lineTo(inset.right() - inset.width() * 0.2, inset.bottom())
        path.lineTo(inset.left() + inset.width() * 0.2, inset.bottom())
        path.lineTo(inset.left(), inset.top() + inset.height() * 0.38)
        path.closeSubpath()
        p.drawPath(path)
    return _make_icon(_draw)


@functools.lru_cache(maxsize=None)
def icon_draw_rectangle() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        p.setPen(_pen(color, 1.8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(rect.adjusted(3, 5, -3, -5))
    return _make_icon(_draw)


@functools.lru_cache(maxsize=None)
def icon_draw_circle() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        p.setPen(_pen(color, 1.8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect.adjusted(3, 3, -3, -3))
    return _make_icon(_draw)


@functools.lru_cache(maxsize=None)
def icon_draw_ring() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        p.setPen(_pen(color, 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect.adjusted(2, 2, -2, -2))
        p.drawEllipse(rect.adjusted(7, 7, -7, -7))
    return _make_icon(_draw)


@functools.lru_cache(maxsize=None)
def icon_vertices() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        pen = _pen(color, 1.6)
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        start = rect.bottomLeft() + QPointF(4, -4)
        mid = rect.center()
        end = rect.topRight() + QPointF(-4, 4)
        p.drawLine(start, mid)
        p.drawLine(mid, end)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        for pt in (start, mid, end):
            p.drawRect(QRectF(pt.x() - 1.5, pt.y() - 1.5, 3, 3))
    return _make_icon(_draw)


@functools.lru_cache(maxsize=None)
def icon_delete() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        p.setPen(_pen(color, 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        body = rect.adjusted(5, 7, -5, -2)
        p.drawRect(body)
        p.drawLine(QPointF(rect.left() + 3, rect.top() + 7), QPointF(rect.right() - 3, rect.top() + 7))
        p.drawLine(QPointF(rect.center().x() - 3, rect.top() + 4), QPointF(rect.center().x() + 3, rect.top() + 4))
        for frac in (-0.2, 0.0, 0.2):
            x = body.center().x() + body.width() * frac
            p.drawLine(QPointF(x, body.top() + 2), QPointF(x, body.bottom() - 2))
    return _make_icon(_draw)


@functools.lru_cache(maxsize=None)
def icon_buffer() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        c = rect.center()
        pen = _pen(color, 1.4)
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(c, rect.width() * 0.4, rect.width() * 0.4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawEllipse(c, rect.width() * 0.08, rect.width() * 0.08)
    return _make_icon(_draw)


@functools.lru_cache(maxsize=None)
def icon_search_grid() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        p.setPen(_pen(color, 1.4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        inset = rect.adjusted(3, 3, -3, -3)
        for i in (1, 2):
            x = inset.left() + inset.width() * i / 3
            p.drawLine(QPointF(x, inset.top()), QPointF(x, inset.bottom()))
            y = inset.top() + inset.height() * i / 3
            p.drawLine(QPointF(inset.left(), y), QPointF(inset.right(), y))
        p.drawRect(inset)
    return _make_icon(_draw)


@functools.lru_cache(maxsize=None)
def icon_search_pattern() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        p.setPen(_pen(color, 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        inset = rect.adjusted(3, 3, -3, -3)
        path = QPainterPath()
        path.moveTo(inset.left(), inset.top())
        path.lineTo(inset.right(), inset.top())
        path.lineTo(inset.right(), inset.center().y())
        path.lineTo(inset.left(), inset.center().y())
        path.lineTo(inset.left(), inset.bottom())
        path.lineTo(inset.right(), inset.bottom())
        p.drawPath(path)
    return _make_icon(_draw)


@functools.lru_cache(maxsize=None)
def icon_convert() -> QIcon:
    def _draw(p: Painter, rect: QRectF, color: QColor) -> None:
        p.setPen(_pen(color, 1.8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        arc_rect = rect.adjusted(4, 4, -4, -4)
        p.drawArc(arc_rect, 30 * 16, 300 * 16)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        angle = math.radians(30)
        tip = QPointF(
            arc_rect.center().x() + arc_rect.width() * 0.5 * math.cos(angle),
            arc_rect.center().y() - arc_rect.height() * 0.5 * math.sin(angle),
        )
        path = QPainterPath()
        path.moveTo(tip.x() - 3, tip.y() - 4)
        path.lineTo(tip.x() + 4, tip.y() - 1)
        path.lineTo(tip.x() - 1, tip.y() + 4)
        path.closeSubpath()
        p.drawPath(path)
    return _make_icon(_draw)


__all__ = [
    "icon_pan",
    "icon_move",
    "icon_select",
    "icon_zoom_in",
    "icon_zoom_out",
    "icon_prev_extent",
    "icon_next_extent",
    "icon_search",
    "icon_coordinate_entry",
    "icon_my_location",
    "icon_marker",
    "icon_hazard",
    "icon_clue",
    "icon_task_area",
    "icon_measure",
    "icon_extent",
    "icon_clear",
    "icon_zoom_to_selection",
    "icon_draw_point",
    "icon_draw_line",
    "icon_draw_arc",
    "icon_draw_polygon",
    "icon_draw_rectangle",
    "icon_draw_circle",
    "icon_draw_ring",
    "icon_vertices",
    "icon_delete",
    "icon_buffer",
    "icon_search_grid",
    "icon_search_pattern",
    "icon_convert",
]
