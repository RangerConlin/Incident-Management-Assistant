"""Application icon helpers for widgets."""
from __future__ import annotations

import functools
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from .styles import get_palette
from .tokens import ICON_SIZE_MD, ICON_SIZE_SM, ALERT_WARNING, ALERT_DANGER


Painter = QPainter
DrawFn = Callable[[Painter, QRectF], None]


def _make_icon(draw_fn: DrawFn, size: int = ICON_SIZE_MD) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    draw_fn(painter, QRectF(0, 0, size, size))
    painter.end()
    return QIcon(pixmap)


def _outline_pen(color: QColor, width: float = 2.0) -> QPen:
    pen = QPen(color)
    pen.setWidthF(width)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    return pen


@functools.lru_cache(maxsize=None)
def icon_clock_warning() -> QIcon:
    """Return a yellow clock icon used for approaching check-in deadlines."""

    def _draw(p: Painter, rect: QRectF) -> None:
        color = QColor(ALERT_WARNING)
        inset = rect.adjusted(2, 2, -2, -2)
        p.setPen(_outline_pen(color))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(inset)
        center = inset.center()
        p.drawLine(center, QPointF(center.x(), center.y() - inset.height() / 3))
        p.drawLine(center, QPointF(center.x() + inset.width() / 4, center.y()))
    return _make_icon(_draw, ICON_SIZE_MD)


@functools.lru_cache(maxsize=None)
def icon_clock_overdue() -> QIcon:
    """Return a red clock icon representing overdue check-ins."""

    def _draw(p: Painter, rect: QRectF) -> None:
        color = QColor(ALERT_DANGER)
        inset = rect.adjusted(2, 2, -2, -2)
        p.setPen(_outline_pen(color))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(inset)
        center = inset.center()
        p.drawLine(center, QPointF(center.x(), center.y() - inset.height() / 3))
        p.drawLine(center, QPointF(center.x() - inset.width() / 4, center.y()))
    return _make_icon(_draw, ICON_SIZE_MD)


@functools.lru_cache(maxsize=None)
def icon_triangle_warning() -> QIcon:
    """Return a triangular warning indicator used for assistance flags."""

    def _draw(p: Painter, rect: QRectF) -> None:
        color = QColor(ALERT_WARNING)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        path = QPainterPath()
        path.moveTo(rect.center().x(), rect.top() + 2)
        path.lineTo(rect.right() - 2, rect.bottom() - 2)
        path.lineTo(rect.left() + 2, rect.bottom() - 2)
        path.closeSubpath()
        p.drawPath(path)
        p.setBrush(QColor("#1a1a1a"))
        p.drawEllipse(QRectF(rect.center().x() - 1.5, rect.center().y() - 3.0, 3.0, 3.0))
        p.drawRect(QRectF(rect.center().x() - 1.0, rect.center().y(), 2.0, rect.bottom() - rect.center().y() - 3))
    return _make_icon(_draw, ICON_SIZE_MD)


@functools.lru_cache(maxsize=None)
def icon_beacon_emergency() -> QIcon:
    """Return a beacon icon for emergency alerts."""

    def _draw(p: Painter, rect: QRectF) -> None:
        color = QColor(ALERT_DANGER)
        p.setPen(Qt.PenStyle.NoPen)
        base_rect = QRectF(rect.left() + 4, rect.center().y() - 4, rect.width() - 8, rect.height() / 2)
        p.setBrush(color)
        p.drawRoundedRect(base_rect, 3, 3)
        dome_rect = QRectF(base_rect.left(), rect.top() + 2, base_rect.width(), base_rect.height())
        p.drawEllipse(dome_rect)
        glow_color = QColor(color)
        glow_color.setAlpha(120)
        p.setBrush(glow_color)
        p.drawEllipse(QRectF(rect.center().x() - rect.width() / 4, rect.top(), rect.width() / 2, rect.height() / 2))
        ray_pen = _outline_pen(color, 1.5)
        p.setPen(ray_pen)
        for offset in (-rect.width() / 3, rect.width() / 3):
            p.drawLine(QPointF(rect.center().x() + offset, rect.top() + 2), QPointF(rect.center().x() + offset, rect.top() - 2))
    return _make_icon(_draw, ICON_SIZE_MD)


# --- Card glyphs ---------------------------------------------------------

_DEF_TEAM_COLOR = QColor("#77C4F2")
_DEF_TASK_COLOR = QColor("#9CCC65")
_DEF_COMMS_COLOR = QColor("#FFB74D")
_DEF_LOG_COLOR = QColor("#BA68C8")


def _card_base(color: QColor) -> tuple[QColor, QColor]:
    pal = get_palette()
    fg = QColor(pal["fg"])
    fg.setAlpha(220)
    base = QColor(color)
    base.setAlpha(180)
    return fg, base


def _icon_from_path(color: QColor, build_path: Callable[[QRectF], QPainterPath]) -> QIcon:
    def _draw(p: Painter, rect: QRectF) -> None:
        fg, base = _card_base(color)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(base)
        circle_rect = rect.adjusted(1, 1, -1, -1)
        p.drawEllipse(circle_rect)
        p.setBrush(fg)
        path = build_path(circle_rect.adjusted(4, 4, -4, -4))
        p.drawPath(path)
    return _make_icon(_draw, ICON_SIZE_SM)


@functools.lru_cache(maxsize=None)
def icon_card_teams() -> QIcon:
    def _path(rect: QRectF) -> QPainterPath:
        path = QPainterPath()
        center = rect.center()
        radius = min(rect.width(), rect.height()) / 5
        path.addEllipse(QPointF(center.x() - radius * 1.5, center.y() - radius), radius, radius)
        path.addEllipse(QPointF(center.x() + radius * 1.5, center.y() - radius), radius, radius)
        body = QRectF(center.x() - radius * 2.2, center.y() - radius * 0.5, radius * 4.4, radius * 2.6)
        path.addRoundedRect(body, radius, radius)
        return path

    return _icon_from_path(_DEF_TEAM_COLOR, _path)


@functools.lru_cache(maxsize=None)
def icon_card_tasks() -> QIcon:
    def _path(rect: QRectF) -> QPainterPath:
        path = QPainterPath()
        clip = rect.adjusted(0, 2, 0, -2)
        path.addRoundedRect(clip, 2, 2)
        check = QPainterPath()
        start = QPointF(rect.left() + rect.width() * 0.2, rect.center().y())
        mid = QPointF(rect.left() + rect.width() * 0.4, rect.bottom() - rect.height() * 0.2)
        end = QPointF(rect.right() - rect.width() * 0.2, rect.top() + rect.height() * 0.2)
        check.moveTo(start)
        check.lineTo(mid)
        check.lineTo(end)
        path = path.united(check)
        return path

    return _icon_from_path(_DEF_TASK_COLOR, _path)


@functools.lru_cache(maxsize=None)
def icon_card_comms() -> QIcon:
    def _path(rect: QRectF) -> QPainterPath:
        path = QPainterPath()
        center = rect.bottomRight() - QPointF(rect.width() * 0.2, rect.height() * 0.2)
        inner = QPainterPath()
        inner.addEllipse(center, rect.width() * 0.1, rect.height() * 0.1)
        arc1 = QPainterPath()
        arc1.addEllipse(center, rect.width() * 0.25, rect.height() * 0.25)
        arc2 = QPainterPath()
        arc2.addEllipse(center, rect.width() * 0.4, rect.height() * 0.4)
        path = path.united(inner)
        path = path.united(arc1)
        path = path.united(arc2)
        return path

    return _icon_from_path(_DEF_COMMS_COLOR, _path)


@functools.lru_cache(maxsize=None)
def icon_card_logistics() -> QIcon:
    def _path(rect: QRectF) -> QPainterPath:
        path = QPainterPath()
        box1 = QRectF(rect.left(), rect.top() + rect.height() * 0.1, rect.width() * 0.6, rect.height() * 0.35)
        box2 = QRectF(rect.left() + rect.width() * 0.3, rect.center().y(), rect.width() * 0.6, rect.height() * 0.35)
        path.addRoundedRect(box1, 2, 2)
        path.addRoundedRect(box2, 2, 2)
        return path

    return _icon_from_path(_DEF_LOG_COLOR, _path)


__all__ = [
    "icon_clock_warning",
    "icon_clock_overdue",
    "icon_triangle_warning",
    "icon_beacon_emergency",
    "icon_card_teams",
    "icon_card_tasks",
    "icon_card_comms",
    "icon_card_logistics",
]
