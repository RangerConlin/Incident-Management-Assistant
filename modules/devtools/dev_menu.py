"""Developer utilities menu attachment."""

from PySide6.QtGui import QAction
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout

from .panels.template_debug_panel import TemplateDebugPanel


def attach_dev_menu(main_window):
    """Attach a Developer menu with debugging tools to the main window."""
    # Ensure a top-level Developer menu exists on the menubar
    dev_menu = None
    for act in main_window.menuBar().actions():
        if act.text().lower().strip("&") in {"developer", "dev"}:
            dev_menu = act.menu()
            break
    if dev_menu is None:
        dev_menu = main_window.menuBar().addMenu("&Developer")

    act = QAction("Template Debug Panel", main_window)

    def _open():
        panel = TemplateDebugPanel(parent=main_window)

        # Wrap the panel in a modal dialog
        dlg = QDialog(main_window)
        dlg.setWindowTitle("Template Debug")
        dlg.setWindowModality(Qt.ApplicationModal)     # true modal
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)

        v = QVBoxLayout(dlg)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(panel)

        dlg.resize(900, 700)                           # sane default size
        dlg.exec()                                     # blocks until closed

    act.triggered.connect(_open)
    dev_menu.addAction(act)
