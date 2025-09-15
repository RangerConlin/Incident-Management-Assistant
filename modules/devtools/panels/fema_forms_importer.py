from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QCheckBox,
    QTextEdit,
    QLineEdit,
)

from ..services.fema_fetch import fetch_latest, FORM_IDS


class FEMAFormsImporter(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("FEMA ICS Forms Importer")

        v = QVBoxLayout(self)
        v.addWidget(QLabel("Select base ICS forms to fetch (latest available from FEMA):"))
        self.lst = QListWidget(self)
        self.lst.setSelectionMode(QAbstractItemView.MultiSelection)
        for fid in FORM_IDS:
            it = QListWidgetItem(fid)
            it.setSelected(True)
            self.lst.addItem(it)
        v.addWidget(self.lst, 1)

        row = QHBoxLayout()
        self.chk_trim = QCheckBox("Trim instruction pages (keep only form pages)")
        self.chk_trim.setChecked(True)
        row.addWidget(self.chk_trim)
        row.addStretch(1)
        v.addLayout(row)

        # Manual URL fetch
        url_row = QHBoxLayout()
        self.url_edit = QLineEdit(self)
        self.url_edit.setPlaceholderText("Paste direct PDF URL (optional)")
        self.btn_fetch_url = QPushButton("Fetch From URL")
        url_row.addWidget(self.url_edit, 1)
        url_row.addWidget(self.btn_fetch_url)
        v.addLayout(url_row)

        btn_row = QHBoxLayout()
        self.btn_fetch = QPushButton("Fetch & Register")
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_fetch)
        v.addLayout(btn_row)

        self.log = QTextEdit(self)
        self.log.setReadOnly(True)
        v.addWidget(self.log, 1)

        self.btn_fetch.clicked.connect(self._run)
        self.btn_fetch_url.clicked.connect(self._run_url)

    def _run(self) -> None:
        items = self.lst.selectedItems()
        forms: List[str] = [it.text() for it in items]
        trim = self.chk_trim.isChecked()
        try:
            results = fetch_latest(forms, trim_instructions=trim)
            for fid, ver, path in results:
                self.log.append(f"Fetched {fid} v{ver} → {path}")
            if not results:
                self.log.append("No forms fetched; check network or site changes.")
        except Exception as e:
            self.log.append(f"ERROR: {e}")

    def _run_url(self) -> None:
        import urllib.request
        from pathlib import Path
        from ..services.form_identify import guess_form_id_and_version
        from ..services.schema_scaffold import ensure_schema_for_form
        from .form_template_builder import PDF_DIR
        from ..services.form_catalog import FormCatalog, TemplateEntry
        url = (self.url_edit.text() or "").strip()
        if not url:
            self.log.append("Enter a direct PDF URL.")
            return
        try:
            # Use a browser-like request with referer to reduce 403s
            from urllib.parse import urlparse
            parts = urlparse(url)
            origin = f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else None
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
                "Accept": "application/pdf,application/octet-stream,*/*",
                "Accept-Language": "en-US,en;q=0.9",
            }
            if origin:
                headers["Referer"] = origin
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
        except Exception as e:
            self.log.append(f"ERROR fetching URL: {e}")
            return
        tmp = PDF_DIR / "_tmp_download.pdf"
        PDF_DIR.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(data)
        try:
            fid, ver = guess_form_id_and_version(tmp)
        except Exception:
            fid, ver = None, None
        if not fid:
            self.log.append("Could not auto-detect form ID; please use the Catalog Manager → Upload PDF workflow.")
            tmp.unlink(missing_ok=True)
            return
        ver = ver or "latest"
        out = PDF_DIR / f"{fid}_v{ver}.pdf"
        out.write_bytes(tmp.read_bytes())
        tmp.unlink(missing_ok=True)
        try:
            ensure_schema_for_form(fid)
        except Exception:
            pass
        rel = str(out).replace("\\", "/")
        FormCatalog().add_template(fid, TemplateEntry(version=ver, pdf=rel, mapping=None))
        self.log.append(f"Fetched {fid} v{ver} → {rel}")


__all__ = ["FEMAFormsImporter"]
