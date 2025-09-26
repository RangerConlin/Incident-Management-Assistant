"""Developer utilities menu attachment."""

from PySide6.QtGui import QAction
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QMessageBox

from .panels.template_debug_panel import TemplateDebugPanel
from .panels.profile_manager_panel import ProfileManagerPanel
from .panels.form_library_manager import FormLibraryManager
from .panels.dev_cert_catalog_editor import DevCertCatalogEditor
from modules.personnel.services import cert_seeder


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

    # Template Debug
    act_tpl = QAction("Template Debug Panel", main_window)

    def _open_tpl():
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

    act_tpl.triggered.connect(_open_tpl)
    dev_menu.addAction(act_tpl)

    # Manage Profiles
    act_prof = QAction("Manage Profiles…", main_window)

    def _open_prof():
        panel = ProfileManagerPanel(parent=main_window)

        # Wrap the panel in a modal dialog
        dlg = QDialog(main_window)
        dlg.setWindowTitle("Manage Profiles")
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)

        v = QVBoxLayout(dlg)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(panel)

        dlg.resize(800, 600)
        dlg.exec()

    act_prof.triggered.connect(_open_prof)
    dev_menu.addAction(act_prof)

    # Form Library Manager
    act_forms = QAction("Manage Forms…", main_window)

    def _open_forms():
        panel = FormLibraryManager(parent=main_window)
        dlg = QDialog(main_window)
        dlg.setWindowTitle("Manage Forms")
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        v = QVBoxLayout(dlg)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(panel)
        dlg.resize(1100, 720)
        dlg.exec()

    act_forms.triggered.connect(_open_forms)
    dev_menu.addAction(act_forms)

    # Certification Catalog Editor (Developer-only)
    act_cert_editor = QAction("Certification Catalog Editor", main_window)

    def _open_cert_editor():
        try:
            panel = DevCertCatalogEditor(parent=main_window)
        except Exception as e:
            QMessageBox.critical(main_window, "Developer Tools", str(e))
            return

        dlg = QDialog(main_window)
        dlg.setWindowTitle("Certification Catalog Editor")
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        v = QVBoxLayout(dlg)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(panel)
        dlg.resize(1000, 700)
        dlg.exec()

    act_cert_editor.triggered.connect(_open_cert_editor)
    dev_menu.addAction(act_cert_editor)

    # Rerun Catalog Seeder
    act_seed = QAction("Rerun Catalog Seeder", main_window)

    def _run_seed():
        changed, msg = cert_seeder.sync()
        QMessageBox.information(main_window, "Catalog Seeder", msg)

    act_seed.triggered.connect(_run_seed)
    dev_menu.addAction(act_seed)
