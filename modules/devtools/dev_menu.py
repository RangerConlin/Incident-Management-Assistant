from PySide6.QtWidgets import QAction

from .panels.template_debug_panel import TemplateDebugPanel


def attach_dev_menu(main_window):
    """Attach a Tools→Developer→Template Debug Panel action to the main window.
    Call this from your main UI setup when DEV_MODE is true.
    """
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
        panel.setAttribute(panel.WA_DeleteOnClose, True)
        panel.show()

    act.triggered.connect(_open)
    dev_menu.addAction(act)

