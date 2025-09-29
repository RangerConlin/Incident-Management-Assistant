from __future__ import annotations

from typing import Any, Dict, Optional, List

from PySide6.QtCore import Qt, QObject
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTabWidget,
    QSpacerItem,
    QSizePolicy,
)

from .panels.queue_panel import QueuePanel
from .panels.history_panel import HistoryPanel
from .panels.editor_panel import EditorPanel


_open_windows: List[QWidget] = []


def open_editor_window(
    incident_id: str, current_user: Dict[str, Any], message_id: Optional[int] = None
) -> QWidget:
    title = f"Public Information - Edit #{message_id}" if message_id else "Public Information - New Message"

    win = QMainWindow()
    win.setAttribute(Qt.WA_DeleteOnClose, True)
    win.setWindowTitle(title)
    editor = EditorPanel(incident_id, current_user, message_id)
    win.setCentralWidget(editor)

    def _cleanup(_obj: Optional[QObject] = None) -> None:
        try:
            _open_windows.remove(win)
        except ValueError:
            pass

    try:
        win.destroyed.connect(_cleanup)
    except Exception:
        pass
    _open_windows.append(win)
    win.resize(900, 650)
    win.show()
    return win


def get_public_info_panel(
    incident_id: str, current_user: Dict[str, Any], parent: Optional[QWidget] = None
) -> QWidget:
    root = QWidget(parent)
    vbox = QVBoxLayout(root)
    vbox.setContentsMargins(8, 8, 8, 8)
    vbox.setSpacing(6)

    # Toolbar row
    toolbar = QHBoxLayout()
    btn_new = QPushButton("New Message")
    btn_filters = QPushButton("Filters")
    btn_filters.setEnabled(False)
    btn_refresh = QPushButton("Refresh")
    toolbar.addWidget(btn_new)
    toolbar.addWidget(btn_filters)
    toolbar.addWidget(btn_refresh)
    toolbar.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
    lbl_status = QLabel("Status: <b>Connected</b>")
    toolbar.addWidget(lbl_status)
    vbox.addLayout(toolbar)

    tabs = QTabWidget()
    queue = QueuePanel(incident_id, current_user)
    history = HistoryPanel(incident_id)
    tabs.addTab(queue, "Queue")
    tabs.addTab(history, "History")
    vbox.addWidget(tabs)

    # Wiring
    def _open_new():
        w = open_editor_window(incident_id, current_user, None)
        try:
            w.destroyed.connect(lambda _=None: (queue.refresh(), history.refresh()))
        except Exception:
            pass

    btn_new.clicked.connect(_open_new)

    def _refresh_all():
        queue.refresh()
        history.refresh()

    btn_refresh.clicked.connect(_refresh_all)

    # Double-click open from queue
    queue.messageActivated.connect(lambda mid: _open_existing(mid))

    def _open_existing(message_id: int):
        if not message_id:
            return
        w = open_editor_window(incident_id, current_user, message_id)
        try:
            w.destroyed.connect(lambda _=None: (queue.refresh(), history.refresh()))
        except Exception:
            pass

    # Initial refresh
    _refresh_all()

    # Keyboard shortcuts for dashboard
    QShortcut(QKeySequence("N"), root, activated=_open_new)
    QShortcut(QKeySequence("R"), root, activated=_refresh_all)
    QShortcut(QKeySequence("F"), root, activated=lambda: queue.focus_first_filter())
    QShortcut(QKeySequence("H"), root, activated=lambda: None)  # placeholder

    return root


def get_media_releases_panel(
    incident_id: str, current_user: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None
) -> QWidget:
    # Fallback: derive a minimal current_user from AppState if not provided
    if current_user is None:
        try:
            from utils.state import AppState

            uid = AppState.get_active_user_id()
            role = AppState.get_active_user_role()
            current_user = {"id": uid, "roles": ([] if not role else [role])}
        except Exception:
            current_user = {"id": None, "roles": []}
    return get_public_info_panel(incident_id, current_user, parent)


def get_inquiries_panel(
    incident_id: str, current_user: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None
) -> QWidget:
    root = QWidget(parent)
    v = QVBoxLayout(root)
    v.addStretch()
    label = QLabel("Public inquiries tracking: under development.")
    label.setAlignment(Qt.AlignCenter)
    v.addWidget(label)
    v.addStretch()
    return root

