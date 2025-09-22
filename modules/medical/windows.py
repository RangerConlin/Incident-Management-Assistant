"""PySide6 helpers for launching the ICS 206 management workflow."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from modules.devtools.panels.form_library_manager import FormLibraryManager

__all__ = ["get_206_panel", "open_206_window"]


def _launch_form_manager(parent: QWidget | None) -> None:
    """Open the consolidated form manager focused on ICS 206."""

    dialog = QDialog(parent)
    dialog.setWindowTitle("Manage Forms — ICS 206")
    dialog.setAttribute(Qt.WA_DeleteOnClose, True)

    layout = QVBoxLayout(dialog)
    manager = FormLibraryManager(dialog)
    layout.addWidget(manager)
    manager.focus_form("ICS_206")

    dialog.resize(1100, 720)
    dialog.exec()


def open_206_window(parent: QWidget | None = None) -> None:
    """Present guidance for managing the ICS 206 medical plan."""

    info_dialog = QDialog(parent)
    info_dialog.setWindowTitle("Medical Plan (ICS 206)")
    info_dialog.setAttribute(Qt.WA_DeleteOnClose, True)

    layout = QVBoxLayout(info_dialog)

    message = QLabel(
        "The ICS 206 medical plan is now authored through the consolidated "
        "Form Library Manager. Use the button below to review templates, "
        "assign profiles, and edit bindings for the incident medical plan."
    )
    message.setWordWrap(True)
    layout.addWidget(message)

    button_row = QHBoxLayout()
    open_button = QPushButton("Open Manage Forms")
    open_button.clicked.connect(lambda: _launch_form_manager(info_dialog))
    button_row.addStretch(1)
    button_row.addWidget(open_button)
    layout.addLayout(button_row)

    buttons = QDialogButtonBox(QDialogButtonBox.Close)
    buttons.rejected.connect(info_dialog.reject)
    buttons.accepted.connect(info_dialog.accept)
    layout.addWidget(buttons)

    info_dialog.resize(520, 220)
    info_dialog.exec()


def get_206_panel(_incident_id: Optional[object] = None) -> QWidget:
    """Return a lightweight panel pointing operators to the new workflow."""

    panel = QWidget()
    layout = QVBoxLayout(panel)

    title = QLabel("Medical Plan (ICS 206)")
    title.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title)

    body = QLabel(
        "Use the Form Library Manager to manage ICS 206 templates, map PDF "
        "fields to bindings, and assign the medical plan to incident profiles."
    )
    body.setWordWrap(True)
    layout.addWidget(body)

    open_button = QPushButton("Open Manage Forms")
    open_button.clicked.connect(lambda: _launch_form_manager(panel))
    layout.addWidget(open_button)

    layout.addStretch(1)
    return panel

