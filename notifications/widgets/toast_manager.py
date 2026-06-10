from __future__ import annotations

from typing import Dict, Any, Optional

from PySide6.QtCore import Qt, QTimer, QEasingCurve, Property
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


class _ToastItem(QFrame):
    def __init__(self, payload: Dict[str, Any], *, default_duration: int = 4500, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ToastItem")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)

        title = str(payload.get("title") or "")
        message = str(payload.get("message") or "")
        severity = str(payload.get("severity") or "info")
        mode = str(payload.get("toast_mode") or "auto")
        duration = int(payload.get("toast_duration_ms") or default_duration)

        # Basic layout
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(12, 10, 12, 10)
        vbox.setSpacing(6)

        row = QHBoxLayout()
        row.setSpacing(8)

        title_lbl = QLabel(title)
        f = QFont()
        f.setBold(True)
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
            msg_lbl.setWordWrap(True)
            msg_lbl.setObjectName("toastMessage")
            vbox.addWidget(msg_lbl)

        # Severity-based styling via objectName + dynamic property
        self.setProperty("severity", severity)
        self.setStyleSheet(
            """
            QFrame#ToastItem { border-radius: 6px; border: 1px solid palette(dark); }
            QFrame#ToastItem[severity="info"] { background: rgba(56, 121, 217, 0.10); }
            QFrame#ToastItem[severity="success"] { background: rgba(56, 217, 120, 0.12); }
            QFrame#ToastItem[severity="warning"] { background: rgba(217, 169, 56, 0.14); }
            QFrame#ToastItem[severity="error"] { background: rgba(217, 56, 56, 0.12); }
            QPushButton#toastClose { border: none; background: transparent; }
            QPushButton#toastClose:hover { background: rgba(0,0,0,0.08); }
            QLabel#toastTitle { margin-right: 6px; }
            """
        )

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
    """Overlay container anchored top-right that stacks toast items.

    Call `enqueue(payload: dict)` to show a toast.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ToastManager")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setWindowFlags(Qt.SubWindow)

        self._margin = 8
        self._max_width = 360
        self._max_items = 4

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._layout.addStretch(1)

        # Ensure on top of siblings
        self.raise_()

    # Public API -------------------------------------------------------------
    def enqueue(self, payload: Dict[str, Any]) -> None:
        # Enforce a cap on visible toasts
        self._prune_to_max()

        item = _ToastItem(payload, parent=self)
        # Insert above the stretch so newest appear at the top
        idx = max(0, self._layout.count() - 1)
        self._layout.insertWidget(idx, item)
        item.destroyed.connect(lambda *_: self._reflow())  # type: ignore[arg-type]
        self._reflow()

    def reflow(self) -> None:
        self._reflow()

    # Internals --------------------------------------------------------------
    def _reflow(self) -> None:
        parent = self.parentWidget()
        if not parent:
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
            self.hide()
            return

        # Position at top-right of parent
        x = parent.width() - max_w - self._margin
        y = self._margin
        self.setGeometry(max(x, 0), y, max_w, min(total_h, parent.height()))
        self.raise_()

    def _prune_to_max(self) -> None:
        # Remove oldest items beyond the cap
        items = [self._layout.itemAt(i).widget() for i in range(self._layout.count())]
        visible = [w for w in items if isinstance(w, _ToastItem)]
        overflow = max(0, len(visible) + 1 - self._max_items)
        for w in visible[:overflow]:
            if w is not None:
                w.deleteLater()
