from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Optional
import json

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QTextEdit,
    QDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QInputDialog,
    QMessageBox,
    QFileDialog,
)

from utils.profile_manager import profile_manager, ProfileMeta
from notifications.services import get_notifier


class ProfileManagerPanel(QWidget):
    """Simple UI to view, validate, and switch profiles.

    - Lists discovered profiles
    - Shows which profile is active
    - Actions: Activate, Lint, Hot Reload, Open Folder
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowTitle("Manage Profiles")

        self._list = QListWidget(self)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)

        # Header / info
        self._active_label = QLabel("")
        self._path_label = QLabel("")
        self._path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        # Actions
        self._btn_activate = QPushButton("Activate")
        self._btn_lint = QPushButton("Lint")
        self._btn_reload = QPushButton("Hot Reload")
        self._btn_open = QPushButton("Open Folder")
        self._btn_new = QPushButton("Add Profile…")
        self._btn_rename = QPushButton("Rename Profile…")
        self._btn_delete = QPushButton("Delete Profile…")
        self._btn_templates = QPushButton("Manage Templates…")
        self._btn_upload = QPushButton("Upload Form…")

        self._btn_activate.clicked.connect(self._activate_selected)
        self._btn_lint.clicked.connect(self._lint_selected)
        self._btn_reload.clicked.connect(self._hot_reload)
        self._btn_open.clicked.connect(self._open_selected_folder)
        self._btn_new.clicked.connect(self._create_profile)
        self._btn_rename.clicked.connect(self._rename_profile)
        self._btn_delete.clicked.connect(self._delete_profile)
        self._btn_templates.clicked.connect(self._manage_templates)
        self._btn_upload.clicked.connect(self._upload_form)

        # Output area for lint issues / status messages
        self._output = QTextEdit(self)
        self._output.setReadOnly(True)

        # Layout
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.addWidget(QLabel("Discovered Profiles:"))
        v.addWidget(self._list, 1)

        v.addWidget(self._active_label)
        v.addWidget(self._path_label)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self._btn_activate)
        btn_row.addWidget(self._btn_lint)
        btn_row.addWidget(self._btn_reload)
        btn_row.addWidget(self._btn_open)
        btn_row.addSpacing(12)
        btn_row.addWidget(self._btn_new)
        btn_row.addWidget(self._btn_rename)
        btn_row.addWidget(self._btn_delete)
        btn_row.addSpacing(12)
        btn_row.addWidget(self._btn_templates)
        btn_row.addWidget(self._btn_upload)
        btn_row.addStretch(1)
        v.addLayout(btn_row)

        v.addWidget(QLabel("Output:"))
        v.addWidget(self._output, 1)

        self._refresh()

    # ------------------------------------------------------------------ helpers
    def _refresh(self, keep_selected: bool = True) -> None:
        active_id = profile_manager.get_active_profile_id()
        selected_id: Optional[str] = None
        if keep_selected:
            item = self._list.currentItem()
            if item is not None:
                selected_id = item.data(Qt.UserRole)

        self._list.clear()
        for meta in profile_manager.list_profiles():
            text = f"{meta.name}  ({meta.id})"
            if meta.id == active_id:
                text = " ".join(["aCTIVEa", text]).replace("\u001f", " ")  # lightweight active marker
            it = QListWidgetItem(text)
            it.setData(Qt.UserRole, meta.id)
            it.setData(Qt.UserRole + 1, meta)  # store full meta for quick access
            self._list.addItem(it)

        # reselect previously selected or active
        target = selected_id or active_id
        if target is not None:
            for i in range(self._list.count()):
                it = self._list.item(i)
                if it.data(Qt.UserRole) == target:
                    self._list.setCurrentRow(i)
                    break

        self._update_info_labels()

    def _current_meta(self) -> Optional[ProfileMeta]:
        it = self._list.currentItem()
        if not it:
            return None
        meta = it.data(Qt.UserRole + 1)
        if isinstance(meta, ProfileMeta):
            return meta
        return None

    def _update_info_labels(self) -> None:
        active_id = profile_manager.get_active_profile_id() or "<none>"
        self._active_label.setText(f"Active Profile: {active_id}")
        meta = self._current_meta()
        self._path_label.setText(f"Selected Path: {str(meta.path) if meta else ''}")

    def _on_selection_changed(self) -> None:
        self._update_info_labels()

    # ------------------------------------------------------------------ actions
    def _activate_selected(self) -> None:
        meta = self._current_meta()
        if not meta:
            return
        try:
            profile_manager.set_active_profile(meta.id)
            self._append_output(f"Activated profile: {meta.name} ({meta.id})")
            # Try to show a toast like the main menu action
            try:
                notifier = get_notifier()
                notifier.showToast.emit({
                    "title": "Profile",
                    "message": f"Profile switched to {meta.name}",
                })
            except Exception:
                pass
        except Exception as e:
            self._append_output(f"ERROR activating profile: {e}")
        self._refresh(keep_selected=False)

    def _lint_selected(self) -> None:
        meta = self._current_meta()
        if not meta:
            return
        try:
            issues = profile_manager.lint_profile(meta.id)
            if not issues:
                self._append_output(f"Lint OK for {meta.id} (no issues)")
                return
            # group by level
            errors = [i for i in issues if getattr(i, "level", "").upper() == "ERROR"]
            warns = [i for i in issues if getattr(i, "level", "").upper() != "ERROR"]
            if errors:
                self._append_output(f"Errors ({len(errors)}):")
                for i in errors:
                    self._append_output(f"  - {i.code}: {i.message} @ {i.path}")
            if warns:
                self._append_output(f"Warnings ({len(warns)}):")
                for i in warns:
                    self._append_output(f"  - {i.code}: {i.message} @ {i.path}")
        except Exception as e:
            self._append_output(f"ERROR linting profile: {e}")

    def _hot_reload(self) -> None:
        try:
            profile_manager.hot_reload()
            self._append_output("Profiles reloaded from disk")
        except Exception as e:
            self._append_output(f"ERROR hot reloading profiles: {e}")
        self._refresh()

    def _open_selected_folder(self) -> None:
        meta = self._current_meta()
        if not meta:
            return
        p: Path = meta.path
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))
            self._append_output(f"Opened folder: {p}")
        except Exception as e:
            self._append_output(f"ERROR opening folder: {e}")

    # ------------------------- manage profiles -------------------------
    def _create_profile(self) -> None:
        pid, ok = QInputDialog.getText(self, "New Profile", "Profile ID:")
        if not ok or not pid.strip():
            return
        name, ok2 = QInputDialog.getText(self, "New Profile", "Profile Name:")
        if not ok2:
            return
        try:
            profile_manager.create_profile(pid.strip(), name=name.strip())
            self._append_output(f"Created profile: {pid.strip()}")
            self._refresh(keep_selected=False)
        except Exception as e:
            QMessageBox.critical(self, "Create Profile", str(e))

    def _delete_profile(self) -> None:
        meta = self._current_meta()
        if not meta:
            return
        if meta.id == (profile_manager.get_active_profile_id() or ""):
            QMessageBox.warning(self, "Delete Profile", "Cannot delete the active profile.")
            return
        confirm = QMessageBox.question(
            self,
            "Delete Profile",
            f"Delete profile '{meta.name}' ({meta.id})? This cannot be undone.",
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            profile_manager.delete_profile(meta.id)
            self._append_output(f"Deleted profile: {meta.id}")
            self._refresh(keep_selected=False)
        except Exception as e:
            QMessageBox.critical(self, "Delete Profile", str(e))

    def _rename_profile(self) -> None:
        meta = self._current_meta()
        if not meta:
            return
        new_name, ok = QInputDialog.getText(self, "Rename Profile", "Profile Name:", text=meta.name)
        if not ok:
            return
        try:
            profile_manager.set_profile_name(meta.id, new_name.strip())
            self._append_output(f"Renamed profile '{meta.id}' to '{new_name.strip()}'")
            self._refresh(keep_selected=True)
        except Exception as e:
            QMessageBox.critical(self, "Rename Profile", str(e))

    # ------------------------- templates dialog ------------------------
    def _manage_templates(self) -> None:
        meta = self._current_meta()
        if not meta:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Manage Templates — {meta.name}")
        layout = QVBoxLayout(dlg)

        table = QTableWidget(0, 2, dlg)
        table.setHorizontalHeaderLabels(["Form", "Active Version"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        layout.addWidget(QLabel("Assign active versions for available forms:"))
        layout.addWidget(table)

        forms = profile_manager.list_forms()
        versions_map = profile_manager.list_form_versions(meta.id)

        # populate rows
        for fid in forms:
            table.insertRow(table.rowCount())
            r = table.rowCount() - 1
            table.setItem(r, 0, QTableWidgetItem(fid))
            from PySide6.QtWidgets import QComboBox
            cbo = QComboBox()
            versions = sorted(versions_map.get(fid, []))
            for v in versions:
                cbo.addItem(v)
            # show current active
            act = profile_manager.get_active_template_version(meta.id, fid)
            if act and act in versions:
                cbo.setCurrentText(act)
            table.setCellWidget(r, 1, cbo)

        # buttons
        row = QHBoxLayout()
        btn_save = QPushButton("Save")
        btn_cancel = QPushButton("Close")
        row.addStretch(1)
        row.addWidget(btn_save)
        row.addWidget(btn_cancel)
        layout.addLayout(row)

        def _save():
            for r in range(table.rowCount()):
                fid = table.item(r, 0).text() if table.item(r, 0) else ""
                cbo = table.cellWidget(r, 1)
                if not fid or not cbo:
                    continue
                ver = cbo.currentText().strip()
                if ver:
                    profile_manager.set_active_template_version(meta.id, fid, ver)
            self._append_output("Saved active template versions")
            dlg.accept()

        btn_save.clicked.connect(_save)
        btn_cancel.clicked.connect(dlg.reject)
        dlg.resize(560, 420)
        dlg.exec()

    # ------------------------- upload form -----------------------------
    def _upload_form(self) -> None:
        meta = self._current_meta()
        if not meta:
            return
        fn, _ = QFileDialog.getOpenFileName(self, "Choose a fillable PDF", "", "PDF Files (*.pdf)")
        if not fn:
            return
        form_id, ok = QInputDialog.getText(self, "Form ID", "e.g., ICS_205")
        if not ok or not form_id.strip():
            return
        version, ok2 = QInputDialog.getText(self, "Version", "e.g., 2025.09")
        if not ok2 or not version.strip():
            return

        # Copy PDF into profile and create a v2 template JSON with fingerprint
        try:
            from modules.forms.export import sha256_of_file
        except Exception:
            from pathlib import Path as _P
            def sha256_of_file(p: _P) -> str:
                import hashlib
                h = hashlib.sha256()
                with open(p, 'rb') as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        h.update(chunk)
                return "sha256:" + h.hexdigest()

        try:
            src = Path(fn)
            rel_pdf = Path("assets") / "forms" / form_id.upper() / f"{form_id.upper()}_v{version}.pdf"
            dst_pdf = Path(meta.path) / rel_pdf
            dst_pdf.parent.mkdir(parents=True, exist_ok=True)
            dst_pdf.write_bytes(src.read_bytes())
            fp = sha256_of_file(dst_pdf)

            tpl = {
                "template_version": 2,
                "profile_id": meta.id,
                "form_id": form_id.upper(),
                "form_version": str(version),
                "template_uid": f"{meta.id}:{form_id.upper()}@{version}",
                "title": f"{form_id.upper()} {version}",
                "renderer": "pdf",
                "pdf_source": str(rel_pdf).replace("\\", "/"),
                "pdf_fingerprint": fp,
                "fields": [
                    {"name": "IncidentName", "key": "IncidentName", "label": "Incident Name", "type": "text", "binding": {"source": "constants", "key": "incident.name"}},
                ],
            }
            tpl_name = f"{form_id.upper()}_{version}_template.json"
            tpl_path = Path(meta.path) / "templates" / tpl_name
            tpl_path.write_text(json.dumps(tpl, indent=2), encoding="utf-8")

            # Activate version for this form
            profile_manager.set_active_template_version(meta.id, form_id.upper(), str(version))

            self._append_output(f"Uploaded form and created template: {tpl_path}")
            self._refresh()
        except Exception as e:
            QMessageBox.critical(self, "Upload Form", f"Failed to upload/register form:\n{e}")

    # ------------------------------------------------------------------ output
    def _append_output(self, text: str) -> None:
        self._output.append(text)


__all__ = ["ProfileManagerPanel"]
