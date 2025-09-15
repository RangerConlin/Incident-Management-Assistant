from __future__ import annotations

from pathlib import Path
from typing import Optional, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)

from ..services.form_catalog import FormCatalog, TemplateEntry
from ..services.form_identify import guess_form_id_and_version
from ..services.pdf_mapgen import extract_acroform_fields, generate_map, extract_schema_paths


PDF_DIR = Path("data/forms/pdfs")
MAP_DIR = Path("data/forms/maps")


class FormTemplateBuilder(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Form Template Builder")

        self.catalog = FormCatalog()
        self.pdf_path: Optional[Path] = None

        v = QVBoxLayout(self)

        row = QHBoxLayout()
        self.lbl_pdf = QLabel("No PDF chosen")
        btn_choose = QPushButton("Choose PDF…")
        btn_choose.clicked.connect(self._choose_pdf)
        row.addWidget(self.lbl_pdf)
        row.addWidget(btn_choose)
        row.addStretch(1)
        v.addLayout(row)

        meta_row = QHBoxLayout()
        self.txt_form_id = QLineEdit()
        self.txt_form_id.setPlaceholderText("Form ID (e.g., ICS_205)")
        self.txt_version = QLineEdit()
        self.txt_version.setPlaceholderText("Version (e.g., 2025.09)")
        meta_row.addWidget(QLabel("Form ID:"))
        meta_row.addWidget(self.txt_form_id)
        meta_row.addWidget(QLabel("Version:"))
        meta_row.addWidget(self.txt_version)
        v.addLayout(meta_row)

        v.addWidget(QLabel("Fields (auto-extracted):"))
        self.tbl_fields = QTableWidget(0, 2, self)
        self.tbl_fields.setHorizontalHeaderLabels(["PDF Field", "Binding"])
        self.tbl_fields.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tbl_fields.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        v.addWidget(self.tbl_fields, 1)

        btns = QHBoxLayout()
        self.btn_scan = QPushButton("Scan & Suggest")
        self.btn_save = QPushButton("Save Template")
        btns.addStretch(1)
        btns.addWidget(self.btn_scan)
        btns.addWidget(self.btn_save)
        v.addLayout(btns)

        self.btn_scan.clicked.connect(self._scan)
        self.btn_save.clicked.connect(self._save)

    # ------------------------------- helpers --------------------------------
    def set_source(self, pdf_path: Path, form_id: Optional[str] = None, version: Optional[str] = None) -> None:
        """Seed the builder with a known PDF and optional id/version, then scan."""
        self.pdf_path = Path(pdf_path)
        self.lbl_pdf.setText(self.pdf_path.name)
        if form_id:
            self.txt_form_id.setText(str(form_id))
        if version:
            self.txt_version.setText(str(version))
        # auto-scan to populate table
        self._scan()

    # ------------------------------- actions -------------------------------
    def _choose_pdf(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Choose a fillable PDF", "", "PDF Files (*.pdf)")
        if not fn:
            return
        self.pdf_path = Path(fn)
        self.lbl_pdf.setText(self.pdf_path.name)
        # guess id/version
        fid, ver = guess_form_id_and_version(self.pdf_path)
        if fid:
            self.txt_form_id.setText(fid)
        if ver:
            self.txt_version.setText(ver)

    def _scan(self):
        if not self.pdf_path:
            QMessageBox.warning(self, "Select PDF", "Choose a PDF first.")
            return
        # Extract fields and suggest mappings using schema if available
        fields = extract_acroform_fields(self.pdf_path)
        fid = (self.txt_form_id.text() or "").strip()
        ver = (self.txt_version.text() or "").strip()
        schema_path = Path("modules/forms/schemas") / (fid.lower() + ".schema.json") if fid else None
        tmp_map = MAP_DIR / f"{fid or 'form'}_v{ver or 'x'}.map.yaml"
        try:
            mapping = generate_map(self.pdf_path, fid or "form", ver or "x", tmp_map, schema_path if schema_path and schema_path.exists() else None, None)
        except Exception:
            mapping = {"fields": {f.name: "" for f in fields}}
        # Prepare candidate list for a simple searchable combo
        candidates: List[str] = []
        try:
            if schema_path and schema_path.exists():
                candidates = extract_schema_paths(schema_path, None) or []
        except Exception:
            candidates = []
        from PySide6.QtWidgets import QComboBox
        self.tbl_fields.setRowCount(0)
        for f in fields:
            r = self.tbl_fields.rowCount()
            self.tbl_fields.insertRow(r)
            self.tbl_fields.setItem(r, 0, QTableWidgetItem(f.name))
            cbo = QComboBox()
            cbo.setEditable(True)
            for c in candidates:
                cbo.addItem(c)
            pre = str(mapping.get("fields", {}).get(f.name, ""))
            if pre:
                cbo.setCurrentText(pre)
            self.tbl_fields.setCellWidget(r, 1, cbo)

    def _save(self):
        # Validation
        if not self.pdf_path:
            QMessageBox.warning(self, "Missing", "Choose a PDF first.")
            return
        fid = (self.txt_form_id.text() or "").strip()
        ver = (self.txt_version.text() or "").strip()
        if not fid or not ver:
            QMessageBox.warning(self, "Missing", "Form ID and Version are required.")
            return
        # store PDF under data/forms/pdfs
        PDF_DIR.mkdir(parents=True, exist_ok=True)
        MAP_DIR.mkdir(parents=True, exist_ok=True)
        pdf_name = f"{fid}_v{ver}.pdf"
        dst_pdf = PDF_DIR / pdf_name
        if str(self.pdf_path.resolve()) != str(dst_pdf.resolve()):
            dst_pdf.write_bytes(self.pdf_path.read_bytes())

        # build mapping YAML from table
        mapping_path = MAP_DIR / f"{fid}_v{ver}.map.yaml"
        # Re-run generate_map to ensure YAML structure; then patch with table edits
        mapping = generate_map(dst_pdf, fid, ver, mapping_path, None, None)
        # apply table edits
        for r in range(self.tbl_fields.rowCount()):
            k = self.tbl_fields.item(r, 0).text() if self.tbl_fields.item(r, 0) else ""
            editor = self.tbl_fields.cellWidget(r, 1)
            val = ""
            if editor is not None and hasattr(editor, 'currentText'):
                val = editor.currentText().strip()
            if k:
                mapping["fields"][k] = val
        # save YAML
        try:
            import yaml
            mapping_path.write_text(yaml.dump(mapping, sort_keys=False, allow_unicode=True), encoding="utf-8")
        except Exception:
            pass

        # register in catalog
        rel_pdf = str(dst_pdf).replace("\\", "/")
        rel_map = str(mapping_path).replace("\\", "/")
        self.catalog.add_template(fid, TemplateEntry(version=ver, pdf=rel_pdf, mapping=rel_map))

        QMessageBox.information(self, "Saved", f"Registered {fid} {ver} and stored mapping.")


__all__ = ["FormTemplateBuilder"]
