from __future__ import annotations

import logging
from typing import Dict, Any, Optional

from PySide6.QtCore import Qt, QTimer, QEasingCurve, Property, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QGraphicsOpacityEffect,
)
from utils.styles import notification_colors, subscribe_theme

logger = logging.getLogger(__name__)


class _ToastItem(QFrame):
    clicked = Signal(str)

    def __init__(self, payload: Dict[str, Any], *, default_duration: int = 4500, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ToastItem")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setMinimumHeight(120)

        title = str(payload.get("title") or "")
        message = str(payload.get("message") or "")
        severity = str(payload.get("severity") or "routine")
        category = str(payload.get("category") or "operations")
        mode = str(payload.get("toast_mode") or "auto")
        duration = int(payload.get("toast_duration_ms") or default_duration)
        logger.debug(
            "Constructing toast id=%s title=%r category=%s severity=%s mode=%s duration_ms=%d",
            payload.get("id"), title, category, severity, mode, duration,
        )

        severity_colors, category_colors = notification_colors()
        category_style = category_colors.get(category, category_colors["system"])
        cat_text = category_style["label"]
        cat_color = category_style["accent"]
        self._severity = severity
        self._category = category
        self._category_label: QLabel | None = None
        self._apply_theme()
        subscribe_theme(self, lambda _name: self._apply_theme())

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(18, 14, 14, 14)
        vbox.setSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(6)

        if cat_text and category != "operations":
            cat_lbl = QLabel(cat_text)
            cat_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            cat_lbl.setStyleSheet(
                f"color: {cat_color}; font-size: 10px; font-weight: 700;"
                " padding: 1px 4px; border-radius: 3px;"
                f" border: 1px solid {cat_color};"
            )
            self._category_label = cat_lbl
            row.addWidget(cat_lbl, 0)

        title_lbl = QLabel(title)
        title_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        f = QFont()
        f.setBold(True)
        f.setPointSize(max(f.pointSize() + 2, 12))
        title_lbl.setFont(f)
        title_lbl.setObjectName("toastTitle")
        row.addWidget(title_lbl, 1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setObjectName("toastClose")
        close_btn.clicked.connect(self._on_close_clicked)  # type: ignore[arg-type]
        row.addWidget(close_btn, 0, Qt.AlignRight)

        vbox.addLayout(row)

        if message:
            msg_lbl = QLabel(message)
            msg_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            msg_lbl.setWordWrap(True)
            msg_lbl.setObjectName("toastMessage")
            message_font = msg_lbl.font()
            message_font.setPointSize(max(message_font.pointSize() + 1, 11))
            msg_lbl.setFont(message_font)
            vbox.addWidget(msg_lbl)

        # Opacity effect for fade in/out
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity = 0.0
        self._opacity_effect.setOpacity(self._opacity)

        # Auto-dismiss if mode is auto
        self._timer: Optional[QTimer] = None
        if mode == "auto":
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self.dismiss)  # type: ignore[arg-type]
            self._timer.start(max(1000, duration))

        # Animate fade-in quickly
        self._animate(to=1.0, duration=180)

    # Expose opacity as a Qt property so animations can target it easily
    def _get_opacity(self) -> float:
        return self._opacity

    def _set_opacity(self, value: float) -> None:
        self._opacity = value
        self._opacity_effect.setOpacity(value)

    opacity = Property(float, _get_opacity, _set_opacity)  # type: ignore[assignment]

    def _on_close_clicked(self) -> None:
        self.dismiss()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        notification_id = str(self.property("notification_id") or "")
        if notification_id:
            self.clicked.emit(notification_id)
        super().mousePressEvent(event)

    def _apply_theme(self) -> None:
        severity_colors, category_colors = notification_colors()
        style = severity_colors.get(self._severity, severity_colors["routine"])
        self.setStyleSheet(
            f"QFrame#ToastItem {{ border-radius: 6px; border-left: 3px solid {style['accent']};"
            " border-top: 1px solid palette(dark); border-right: 1px solid palette(dark);"
            f" border-bottom: 1px solid palette(dark); background: {style['background']}; }}"
            " QPushButton#toastClose { border: none; background: transparent; }"
            " QPushButton#toastClose:hover { background: palette(midlight); }"
        )
        if self._category_label is not None:
            category_style = category_colors.get(self._category, category_colors["system"])
            color = category_style["accent"]
            self._category_label.setStyleSheet(
                f"color: {color}; font-size: 10px; font-weight: 700;"
                " padding: 1px 4px; border-radius: 3px;"
                f" border: 1px solid {color};"
            )

    def dismiss(self) -> None:
        # Fade out then remove
        self._animate(to=0.0, duration=160, finished_cb=lambda: self.deleteLater())

    def _animate(self, *, to: float, duration: int, finished_cb=None) -> None:
        from PySide6.QtCore import QPropertyAnimation

        anim = QPropertyAnimation(self, b"opacity", self)
        anim.setDuration(duration)
        anim.setStartValue(self._opacity)
        anim.setEndValue(to)
        anim.setEasingCurve(QEasingCurve.InOutQuad)
        if finished_cb is not None:
            anim.finished.connect(finished_cb)  # type: ignore[arg-type]
        anim.start()


class ToastManager(QWidget):
    """Overlay container anchored bottom-right that stacks toast items.

    Call `enqueue(payload: dict)` to show a toast.
    """

    toastClicked = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ToastManager")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setWindowFlags(Qt.SubWindow)

        self._margin = 18
        self._max_width = 420
        self._max_items = 4

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._layout.addStretch(1)

        # Ensure on top of siblings
        self.raise_()

    # Public API -------------------------------------------------------------
    def enqueue(self, payload: Dict[str, Any]) -> None:
        logger.info(
            "ToastManager enqueue id=%s title=%r visible=%s parent=%s size=%sx%s",
            payload.get("id"), payload.get("title"), self.isVisible(),
            type(self.parentWidget()).__name__ if self.parentWidget() else None,
            self.width(), self.height(),
        )
        # Enforce a cap on visible toasts
        self._prune_to_max()
        try:
            item = _ToastItem(payload, parent=self)
        except Exception:
            logger.exception("ToastManager failed to construct toast payload=%s", payload)
            raise
        item.setProperty("notification_id", str(payload.get("id") or ""))
        item.clicked.connect(self._on_toast_clicked)
        # Insert above the stretch so newest appear at the top
        idx = max(0, self._layout.count() - 1)
        self._layout.insertWidget(idx, item)
        item.destroyed.connect(lambda *_: self._reflow())  # type: ignore[arg-type]
        self._reflow()
        logger.info(
            "ToastManager displayed id=%s geometry=%s visible=%s",
            payload.get("id"), self.geometry().getRect(), self.isVisible(),
        )

    def _on_toast_clicked(self, notification_id: str) -> None:
        logger.info("ToastManager clicked id=%s", notification_id)
        self.toastClicked.emit(notification_id)
        sender = self.sender()
        if isinstance(sender, _ToastItem):
            sender.dismiss()

    def reflow(self) -> None:
        self._reflow()

    # Internals --------------------------------------------------------------
    def _reflow(self) -> None:
        parent = self.parentWidget()
        if not parent:
            logger.warning("ToastManager cannot reflow because it has no parent widget")
            return
        # Compute total height from children
        total_h = self._margin
        max_w = self._max_width
        visible_count = 0
        for i in range(self._layout.count()):
            w = self._layout.itemAt(i).widget()
            if w is None or not isinstance(w, _ToastItem):
                continue
            visible_count += 1
            w.setMaximumWidth(self._max_width)
            w.adjustSize()
            total_h += w.height() + (self._layout.spacing() if i > 0 else 0)
        total_h += self._margin

        if visible_count == 0:
            logger.debug("ToastManager hiding because no toast items remain")
            self.hide()
            return

        # Position at bottom-right of parent. New items sit nearest the
        # corner and older notifications grow upward.
        x = parent.width() - max_w - self._margin
        height = min(total_h, max(1, parent.height() - (self._margin * 2)))
        y = parent.height() - height - self._margin
        self.setGeometry(max(x, 0), max(y, 0), max_w, height)
        self.show()
        self.raise_()

    def _prune_to_max(self) -> None:
        # Remove oldest items beyond the cap
        items = [self._layout.itemAt(i).widget() for i in range(self._layout.count())]
        visible = [w for w in items if isinstance(w, _ToastItem)]
        overflow = max(0, len(visible) + 1 - self._max_items)
        for w in visible[:overflow]:
            if w is not None:
                w.deleteLater()
