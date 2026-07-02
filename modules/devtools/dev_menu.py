"""Developer utilities menu attachment."""

import os
import subprocess
import sys

from PySide6.QtGui import QAction
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QMessageBox, QInputDialog, QLineEdit, QTextEdit

from .panels.template_debug_panel import TemplateDebugPanel
from .panels.profile_manager_panel import ProfileManagerPanel
from .panels.dev_cert_catalog_editor import DevCertCatalogEditor


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

        dlg.adjustSize()
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

        dlg.adjustSize()
        dlg.exec()

    act_prof.triggered.connect(_open_prof)
    dev_menu.addAction(act_prof)


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
        dlg.resize(900, 600)
        dlg.exec()

    act_cert_editor.triggered.connect(_open_cert_editor)
    dev_menu.addAction(act_cert_editor)

    # Forms Creator (Hub: catalog, versions, binding editor)
    act_forms = QAction("Forms Creator…", main_window)

    def _open_forms():
        try:
            from modules.forms_creator.ui.HubWindow import HubWindow
            win = HubWindow(parent=main_window)
            win.setAttribute(Qt.WA_DeleteOnClose, True)
            win.show()
        except Exception as e:
            QMessageBox.critical(main_window, "Developer Tools", str(e))

    act_forms.triggered.connect(_open_forms)
    dev_menu.addAction(act_forms)

    # Sync Local -> Cloud MongoDB
    act_cloud_sync = QAction("Sync Local -> Cloud…", main_window)

    def _run_cloud_sync():
        cloud_uri = os.environ.get("SARAPP_CLOUD_MONGO_URI", "").strip()
        if not cloud_uri:
            cloud_uri, ok = QInputDialog.getText(
                main_window,
                "Sync Local -> Cloud",
                "Cloud MongoDB URI (set SARAPP_CLOUD_MONGO_URI to skip this prompt):",
                QLineEdit.Normal,
            )
            if not ok or not cloud_uri.strip():
                return
            cloud_uri = cloud_uri.strip()

        confirm = QMessageBox.warning(
            main_window,
            "Sync Local -> Cloud",
            "This will REPLACE every master and incident database on the cloud "
            "server with the local copy. Existing cloud-only data will be lost.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        script_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data", "db", "sync_local_to_cloud.py",
        )
        env = os.environ.copy()
        env["SARAPP_CLOUD_MONGO_URI"] = cloud_uri

        try:
            result = subprocess.run(
                [sys.executable, script_path],
                env=env,
                capture_output=True,
                text=True,
                timeout=300,
            )
            output = result.stdout + ("\n" + result.stderr if result.stderr else "")
        except Exception as e:
            output = f"Failed to run sync script: {e}"

        dlg = QDialog(main_window)
        dlg.setWindowTitle("Sync Local -> Cloud — Result")
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        v = QVBoxLayout(dlg)
        text = QTextEdit(dlg)
        text.setReadOnly(True)
        text.setPlainText(output)
        v.addWidget(text)
        dlg.resize(700, 500)
        dlg.exec()

    act_cloud_sync.triggered.connect(_run_cloud_sync)
    dev_menu.addAction(act_cloud_sync)
