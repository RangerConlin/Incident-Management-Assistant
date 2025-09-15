from __future__ import annotations

from typing import Optional
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QInputDialog,
    QMessageBox,
)

from ..services.form_catalog import FormCatalog, FormEntry, TemplateEntry
from utils.profile_manager import profile_manager
from ..services.form_identify import guess_form_id_and_version
from ..services.schema_scaffold import ensure_schema_for_form
from .form_template_builder import FormTemplateBuilder


class FormCatalogManager(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Form Catalog Manager")

        self.catalog = FormCatalog()

        # UI
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Forms (ICS + custom):"))
        row = QHBoxLayout()
        self.lst_forms = QListWidget(self)
        self.lst_forms.currentItemChanged.connect(self._on_select)
        row.addWidget(self.lst_forms, 1)

        right = QVBoxLayout()
        self.lbl_id = QLabel("ID: -")
        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("Title")
        right.addWidget(self.lbl_id)
        right.addWidget(self.txt_title)

        self.txt_profiles = QLineEdit()
        self.txt_profiles.setPlaceholderText("Profiles (comma-separated, e.g., ics_base,ics_us)")
        right.addWidget(QLabel("Active in Profiles:"))
        right.addWidget(self.txt_profiles)

        self.tbl_templates = QTableWidget(0, 3, self)
        self.tbl_templates.setHorizontalHeaderLabels(["Version", "PDF", "Mapping"])
        self.tbl_templates.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl_templates.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_templates.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        right.addWidget(QLabel("Templates:"))
        right.addWidget(self.tbl_templates, 1)

        btns = QHBoxLayout()
        self.btn_add_form = QPushButton("Add Form…")
        self.btn_del_form = QPushButton("Delete Form…")
        self.btn_add_ver = QPushButton("Add Version…")
        self.btn_save = QPushButton("Save")
        self.btn_assign_profiles = QPushButton("Assign Profiles…")
        self.btn_upload_pdf = QPushButton("Upload PDF…")
        btns.addWidget(self.btn_add_form)
        btns.addWidget(self.btn_del_form)
        btns.addStretch(1)
        btns.addWidget(self.btn_assign_profiles)
        btns.addWidget(self.btn_upload_pdf)
        btns.addWidget(self.btn_add_ver)
        btns.addWidget(self.btn_save)
        right.addLayout(btns)

        row.addLayout(right, 2)
        v.addLayout(row)

        # connect
        self.btn_add_form.clicked.connect(self._add_form)
        self.btn_del_form.clicked.connect(self._delete_form)
        self.btn_add_ver.clicked.connect(self._add_version)
        self.btn_save.clicked.connect(self._save)
        self.btn_assign_profiles.clicked.connect(self._assign_profiles)
        self.btn_upload_pdf.clicked.connect(self._upload_pdf)

        self._refresh()

    # -------------------------------- helpers --------------------------------
    def _refresh(self):
        self.lst_forms.clear()
        for f in self.catalog.list_forms():
            it = QListWidgetItem(f"{f.id} — {f.title}")
            it.setData(Qt.UserRole, f)
            self.lst_forms.addItem(it)
        if self.lst_forms.count():
            self.lst_forms.setCurrentRow(0)

    def _on_select(self, cur, prev):
        f: Optional[FormEntry] = cur.data(Qt.UserRole) if cur else None
        self._bind_form(f)

    def _bind_form(self, f: Optional[FormEntry]):
        if not f:
            self.lbl_id.setText("ID: -")
        self.txt_title.setText("")
        self.txt_profiles.setText("")
        self.tbl_templates.setRowCount(0)
        return
        self.lbl_id.setText(f"ID: {f.id}")
        self.txt_title.setText(f.title or f.id)
        self.txt_profiles.setText(",".join(f.profiles or []))
        self.tbl_templates.setRowCount(0)
        for t in f.templates:
            r = self.tbl_templates.rowCount()
            self.tbl_templates.insertRow(r)
            self.tbl_templates.setItem(r, 0, QTableWidgetItem(t.version))
            self.tbl_templates.setItem(r, 1, QTableWidgetItem(t.pdf or ""))
            self.tbl_templates.setItem(r, 2, QTableWidgetItem(t.mapping or ""))

    # -------------------------------- actions --------------------------------
    def _add_form(self):
        fid, ok = QInputDialog.getText(self, "Add Form", "Form ID (e.g., ICS_301 or AGENCY_XYZ):")
        if not ok or not fid.strip():
            return
        entry = FormEntry(id=fid.strip(), title=fid.strip(), category="Custom", profiles=[], templates=[])
        self.catalog.upsert_form(entry, custom=True)
        self._refresh()

    def _delete_form(self):
        cur = self.lst_forms.currentItem()
        if not cur:
            return
        f: FormEntry = cur.data(Qt.UserRole)
        if QMessageBox.question(self, "Delete Form", f"Delete '{f.id}'?") != QMessageBox.Yes:
            return
        self.catalog.delete_form(f.id)
        self._refresh()

    def _add_version(self):
        cur = self.lst_forms.currentItem()
        if not cur:
            return
        f: FormEntry = cur.data(Qt.UserRole)
        ver, ok = QInputDialog.getText(self, "Add Version", "Version (e.g., 2025.09):")
        if not ok or not ver.strip():
            return
        pdf, ok2 = QInputDialog.getText(self, "PDF Path", "Relative PDF path (under data/forms/pdfs):")
        if not ok2:
            return
        map_path, ok3 = QInputDialog.getText(self, "Mapping Path", "Relative Mapping path (optional):")
        if not ok3:
            return
        tpl = TemplateEntry(version=ver.strip(), pdf=pdf.strip(), mapping=(map_path.strip() or None))
        self.catalog.add_template(f.id, tpl)
        self._refresh()

    def _save(self):
        # Only updates title currently
        cur = self.lst_forms.currentItem()
        if not cur:
            return
        f: FormEntry = cur.data(Qt.UserRole)
        f.title = self.txt_title.text().strip() or f.id
        profs = [p.strip() for p in (self.txt_profiles.text() or "").split(",") if p.strip()]
        f.profiles = profs
        self.catalog.upsert_form(f, custom=(f.category == "Custom"))
        QMessageBox.information(self, "Saved", "Catalog updated.")

    def _assign_profiles(self):
        cur = self.lst_forms.currentItem()
        if not cur:
            return
        f: FormEntry = cur.data(Qt.UserRole)
        from PySide6.QtWidgets import QDialog, QListWidget, QListWidgetItem
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Assign Profiles — {f.id}")
        lay = QVBoxLayout(dlg)
        lst = QListWidget(dlg)
        lst.setSelectionMode(QListWidget.MultiSelection)
        ids = [m.id for m in profile_manager.list_profiles()]
        for pid in ids:
            it = QListWidgetItem(pid)
            if pid in (f.profiles or []):
                it.setSelected(True)
            lst.addItem(it)
        lay.addWidget(lst)
        row = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        row.addStretch(1)
        row.addWidget(btn_ok)
        row.addWidget(btn_cancel)
        lay.addLayout(row)
        def _ok():
            selected = [it.text() for it in lst.selectedItems()]
            f.profiles = selected
            # reflect in text field and save
            self.txt_profiles.setText(",".join(selected))
            self.catalog.upsert_form(f, custom=(f.category == "Custom"))
            dlg.accept()
        btn_ok.clicked.connect(_ok)
        btn_cancel.clicked.connect(dlg.reject)
        dlg.resize(360, 440)
        dlg.exec()

    def _upload_pdf(self):
        # 1) Choose PDF
        from PySide6.QtWidgets import QFileDialog
        fn, _ = QFileDialog.getOpenFileName(self, "Choose a fillable PDF", "", "PDF Files (*.pdf)")
        if not fn:
            return
        pdf = Path(fn)
        # 2) Auto-detect and confirm
        fid, ver = guess_form_id_and_version(pdf)
        from PySide6.QtWidgets import QInputDialog
        if not fid:
            fid, ok = QInputDialog.getText(self, "Form ID", "Enter Form ID (e.g., ICS_205):")
            if not ok or not (fid or '').strip():
                return
        else:
            fid, _ = QInputDialog.getText(self, "Form ID", "Confirm Form ID:", text=fid)
        if not ver:
            ver, ok = QInputDialog.getText(self, "Version", "Enter Version (e.g., 2025.09):")
            if not ok or not (ver or '').strip():
                return
        else:
            ver, _ = QInputDialog.getText(self, "Version", "Confirm Version:", text=ver)

        fid = (fid or '').strip()
        ver = (ver or '').strip()
        if not fid or not ver:
            return

        # 3) Ensure schema exists or scaffold
        try:
            schema_path = ensure_schema_for_form(fid)
        except Exception as e:
            QMessageBox.critical(self, "Schema", f"Failed to ensure schema: {e}")
            return

        # 4) Copy PDF to global storage
        from .form_template_builder import PDF_DIR
        PDF_DIR.mkdir(parents=True, exist_ok=True)
        dst_pdf = PDF_DIR / f"{fid}_v{ver}.pdf"
        try:
            dst_pdf.write_bytes(pdf.read_bytes())
        except Exception as e:
            QMessageBox.critical(self, "Copy PDF", f"Failed to copy PDF: {e}")
            return

        # 5) Open builder modal pre-seeded for mapping/bindings
        from PySide6.QtWidgets import QDialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Form Template Builder")
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        lay = QVBoxLayout(dlg)
        panel = FormTemplateBuilder(parent=dlg)
        panel.set_source(dst_pdf, fid, ver)
        lay.addWidget(panel)
        dlg.resize(1000, 760)
        dlg.exec()


__all__ = ["FormCatalogManager"]
