from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QComboBox,
    QLineEdit,
    QSplitter,
    QTextEdit,
    QTreeView,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QGroupBox,
    QFormLayout,
)

from ..services.template_registry import TemplateRegistry
from ..services.pdf_mapgen import generate_map, list_fields
from ..services.renderer_bridge import render_preview

TEMPLATES_ROOT = Path("data/templates")
EXAMPLES_ROOT = Path("data/examples")
REGISTRY_PATH = TEMPLATES_ROOT / "registry.json"


class TemplateDebugPanel(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Template Debug Panel")
        self.resize(1400, 820)

        self.registry = TemplateRegistry(REGISTRY_PATH)

        self.pdf_path: Optional[Path] = None
        self.form_id: str = ""
        self.version: str = ""
        self.domain: str = "ics"  # ics|state|agency|custom
        self.state_code: str = ""  # only used when domain=state
        self.mapping_path: Optional[Path] = None

        self._build_ui()

    # ---------------------------- UI BUILD -----------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # LEFT: Ingest
        left = QWidget()
        left.setMinimumWidth(360)
        left_l = QVBoxLayout(left)
        gb = QGroupBox("Template Ingest")
        form = QFormLayout(gb)
        self.lbl_pdf = QLabel("No file chosen")
        btn_choose = QPushButton("Choose PDF…")
        btn_choose.clicked.connect(self.on_choose_pdf)
        row = QHBoxLayout()
        row.addWidget(self.lbl_pdf)
        row.addWidget(btn_choose)
        form.addRow(QLabel("PDF Template"), row)

        self.cbo_form = QComboBox()
        self.cbo_form.setEditable(True)
        self.cbo_form.addItems([
            "ics_201",
            "ics_205",
            "ics_206",
            "ics_214",
            "ics_218",
        ])  # seed list; editable for any form
        form.addRow("Form ID", self.cbo_form)

        self.txt_version = QLineEdit()
        self.txt_version.setPlaceholderText("e.g., 2025.09")
        form.addRow("Version", self.txt_version)

        self.cbo_domain = QComboBox()
        self.cbo_domain.addItems(["ics", "state", "agency", "custom"])
        self.cbo_domain.currentTextChanged.connect(self.on_domain_change)
        form.addRow("Domain", self.cbo_domain)

        self.cbo_state = QComboBox()
        self.cbo_state.setEditable(True)
        self.cbo_state.setEnabled(False)
        self.cbo_state.addItems(["", "MI", "OH", "IN", "WI", "IL", "PA", "NY"])
        form.addRow("State (if state)", self.cbo_state)

        btn_scan = QPushButton("Scan & Generate Map")
        btn_scan.clicked.connect(self.on_scan_generate)
        btn_register = QPushButton("Validate & Register")
        btn_register.clicked.connect(self.on_validate_register)
        left_l.addWidget(gb)
        left_l.addWidget(btn_scan)
        left_l.addWidget(btn_register)
        left_l.addStretch(1)

        # CENTER: Mapping Editor (simple starter)
        center = QWidget()
        center_l = QVBoxLayout(center)
        self.tbl_fields = QTableWidget(0, 3)
        self.tbl_fields.setHorizontalHeaderLabels(
            ["PDF Field", "Suggested JSON Path", "Formatter"]
        )
        self.tbl_fields.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tbl_fields.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_fields.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        center_l.addWidget(QLabel("Mapping Editor"))
        center_l.addWidget(self.tbl_fields)
        btn_save_map = QPushButton("Save Mapping (.map.yaml)")
        btn_save_map.clicked.connect(self.on_save_map)
        center_l.addWidget(btn_save_map)

        # RIGHT: Preview & Activation
        right = QWidget()
        right_l = QVBoxLayout(right)
        gb2 = QGroupBox("Preview & Activation")
        form2 = QFormLayout(gb2)
        self.cbo_sample = QComboBox()
        self.refresh_samples()
        form2.addRow("Sample JSON", self.cbo_sample)
        btn_preview = QPushButton("Render Preview")
        btn_preview.clicked.connect(self.on_preview)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setPlaceholderText("Logs…")
        btn_activate = QPushButton("Activate Template for Form…")
        btn_activate.clicked.connect(self.on_activate)
        right_l.addWidget(gb2)
        right_l.addWidget(btn_preview)
        right_l.addWidget(self.txt_log)
        right_l.addWidget(btn_activate)

        splitter.addWidget(left)
        splitter.addWidget(center)
        splitter.addWidget(right)
        splitter.setSizes([360, 720, 520])

    # ---------------------------- helpers -------------------------------
    def on_domain_change(self, val: str):
        self.cbo_state.setEnabled(val == "state")

    def refresh_samples(self):
        self.cbo_sample.clear()
        if EXAMPLES_ROOT.exists():
            for p in EXAMPLES_ROOT.glob("*.json"):
                self.cbo_sample.addItem(str(p))

    def on_choose_pdf(self):
        fn, _ = QFileDialog.getOpenFileName(
            self, "Choose a fillable PDF", "", "PDF Files (*.pdf)"
        )
        if fn:
            self.pdf_path = Path(fn)
            self.lbl_pdf.setText(self.pdf_path.name)

    def _domain_folder(self) -> Path:
        if self.cbo_domain.currentText() == "state":
            code = (self.cbo_state.currentText() or "").strip().lower()
            if not code:
                return TEMPLATES_ROOT / "state"
            return TEMPLATES_ROOT / "state" / code
        return TEMPLATES_ROOT / self.cbo_domain.currentText()

    def on_scan_generate(self):
        if not self.pdf_path:
            QMessageBox.warning(self, "Missing PDF", "Choose a fillable PDF first.")
            return
        form_id = self.cbo_form.currentText().strip()
        version = self.txt_version.text().strip()
        if not form_id or not version:
            QMessageBox.warning(self, "Missing data", "Provide Form ID and Version.")
            return

        out_dir = self._domain_folder()
        out_dir.mkdir(parents=True, exist_ok=True)

        # Copy/sanitize PDF name to destination
        pdf_dest = out_dir / f"{form_id.upper()}_v{version}.pdf"
        if str(self.pdf_path.resolve()) != str(pdf_dest.resolve()):
            pdf_dest.write_bytes(Path(self.pdf_path).read_bytes())

        map_dest = out_dir / f"{form_id.upper()}_v{version}.map.yaml"

        # Optional helpers
        sample = Path(self.cbo_sample.currentText()) if self.cbo_sample.currentText() else None
        schema = None

        mapping = generate_map(pdf_dest, form_id, version, map_dest, schema, sample)
        self.mapping_path = map_dest

        # Populate table with fields
        fields = list(mapping.get("fields", {}).items())
        self.tbl_fields.setRowCount(len(fields))
        for r, (pdf_f, suggestion) in enumerate(fields):
            # skip special suggestion block keys
            if pdf_f == "__table_suggestion__":
                continue
            self.tbl_fields.setItem(r, 0, QTableWidgetItem(str(pdf_f)))
            self.tbl_fields.setItem(r, 1, QTableWidgetItem(str(suggestion or "")))
            self.tbl_fields.setItem(r, 2, QTableWidgetItem(""))

        QMessageBox.information(self, "Done", f"Generated mapping → {map_dest}")

    def on_save_map(self):
        if not self.mapping_path:
            QMessageBox.warning(self, "No mapping", "Generate a mapping first.")
            return
        import yaml

        mapping = {
            "form": self.cbo_form.currentText().strip(),
            "version": self.txt_version.text().strip(),
            "fields": {},
        }
        for r in range(self.tbl_fields.rowCount()):
            f = self.tbl_fields.item(r, 0)
            v = self.tbl_fields.item(r, 1)
            fmt = self.tbl_fields.item(r, 2)
            if not f:
                continue
            key = f.text()
            val = (v.text() if v else "").strip()
            formatter = (fmt.text() if fmt else "").strip()
            if formatter:
                mapping["fields"][key] = {"from": val, "fmt": formatter}
            else:
                mapping["fields"][key] = val

        self.mapping_path.write_text(
            yaml.dump(mapping, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        QMessageBox.information(self, "Saved", f"Updated mapping → {self.mapping_path}")

    def on_validate_register(self):
        if not self.mapping_path or not self.mapping_path.exists():
            QMessageBox.warning(self, "Missing mapping", "Generate/save a mapping first.")
            return
        form_id = self.cbo_form.currentText().strip()
        version = self.txt_version.text().strip()
        domain_dir = self._domain_folder()
        pdf_path = domain_dir / f"{form_id.upper()}_v{version}.pdf"
        if not pdf_path.exists():
            QMessageBox.warning(self, "Missing PDF", f"Expected template missing: {pdf_path}")
            return

        self.registry.register(
            form_id=form_id,
            version=version,
            pdf_path=pdf_path,
            mapping_path=self.mapping_path,
            schema_path=None,
            domain=self.cbo_domain.currentText(),
            group=None,
        )
        report = self.registry.validate_entry(form_id, version)
        msg = (
            f"Registered {form_id}:{version}\nCoverage: {report.coverage_pct:.1f}%\n"
            f"Unmapped: {len(report.unmapped_fields)}"
        )
        if report.warnings:
            msg += "\nWarnings:\n- " + "\n- ".join(report.warnings)
        QMessageBox.information(self, "Registry", msg)

    def on_preview(self):
        form_id = self.cbo_form.currentText().strip()
        version = self.txt_version.text().strip()
        domain_dir = self._domain_folder()
        pdf_path = domain_dir / f"{form_id.upper()}_v{version}.pdf"
        map_path = domain_dir / f"{form_id.upper()}_v{version}.map.yaml"
        sample = Path(self.cbo_sample.currentText()) if self.cbo_sample.currentText() else None
        if not (pdf_path.exists() and map_path.exists() and sample and sample.exists()):
            QMessageBox.warning(
                self, "Missing inputs", "Ensure PDF, mapping, and a sample JSON are present."
            )
            return
        try:
            result = render_preview(form_id, version, map_path, sample)
            self.txt_log.setPlainText(result.log)
            QMessageBox.information(
                self,
                "Preview",
                f"Rendered PDF bytes: {len(result.pdf_bytes)}; PNG preview bytes: {len(result.preview_png or b'')} (if supported)",
            )
        except Exception as e:
            self.txt_log.setPlainText(f"Preview failed: {e}")

    def on_activate(self):
        form_id = self.cbo_form.currentText().strip()
        version = self.txt_version.text().strip()
        self.registry.set_active(form_id, version)
        QMessageBox.information(
            self, "Activated", f"Active template set: {form_id} → {version}"
        )

