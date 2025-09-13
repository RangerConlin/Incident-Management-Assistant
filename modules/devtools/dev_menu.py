from PySide6.QtGui import QAction
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout   # <-- add

from .panels.template_debug_panel import TemplateDebugPanel


def attach_dev_menu(main_window):
    """Attach a Tools→Developer→Template Debug Panel action to the main window."""
    tools_menu = None
    for m in main_window.menuBar().actions():
        if m.text().lower().strip("&") == "tools":
            tools_menu = m.menu()
            break
    if not tools_menu:
        tools_menu = main_window.menuBar().addMenu("&Tools")

    dev_menu = tools_menu.addMenu("&Developer")
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
