"""Dialog for creating a new form-set version (template.pdf + mapping scaffold)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from modules.forms_creator.form_set_registry import FormSetMeta


class CreateVersionDialog(QDialog):
    """Let the user pick a form set, version label, and PDF template file."""

    def __init__(
        self,
        form_id: str,
        form_title: str,
        sets: list[FormSetMeta],
        parent=None,
        has_continuation_page: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Create Version — {form_title}")
        self.setMinimumWidth(420)
        self._sets = {s.id: s for s in sets}
        self._continuation_pdf_path: Path | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.set_combo = QComboBox()
        for s in sets:
            self.set_combo.addItem(s.display_name, s.id)
        form.addRow("Form Set", self.set_combo)

        self.version_edit = QLineEdit()
        self.version_edit.setPlaceholderText("e.g. 2023")
        form.addRow("Version Label", self.version_edit)

        pdf_row = QHBoxLayout()
        self.pdf_label = QLabel("No file selected")
        self.pdf_label.setWordWrap(True)
        self._pdf_path: Path | None = None
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_pdf)
        pdf_row.addWidget(self.pdf_label, 1)
        pdf_row.addWidget(browse_btn)
        form.addRow("Template PDF (Page 1)", pdf_row)

        cont_row = QHBoxLayout()
        self._cont_label = QLabel("No file selected  (optional)")
        self._cont_label.setWordWrap(True)
        cont_browse_btn = QPushButton("Browse…")
        cont_browse_btn.clicked.connect(self._browse_continuation_pdf)
        cont_row.addWidget(self._cont_label, 1)
        cont_row.addWidget(cont_browse_btn)
        form.addRow("Continuation PDF (Page 2+)", cont_row)

        info = QLabel(
            "The PDF will be copied into the form set directory and a mapping "
            "scaffold will be generated from its AcroForm fields. The mapper "
            "will open immediately so you can assign bindings."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(info)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Template PDF", "", "PDF Files (*.pdf)"
        )
        if path:
            self._pdf_path = Path(path)
            self.pdf_label.setText(self._pdf_path.name)

    def _browse_continuation_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Continuation PDF", "", "PDF Files (*.pdf)"
        )
        if path:
            self._continuation_pdf_path = Path(path)
            self._cont_label.setText(self._continuation_pdf_path.name)

    def _on_accept(self) -> None:
        set_id = self.set_combo.currentData()
        version = self.version_edit.text().strip()
        if not version:
            QMessageBox.warning(self, "Create Version", "Version label is required.")
            return
        if self._pdf_path is None:
            QMessageBox.warning(self, "Create Version", "Please select a template PDF.")
            return
        self._result = {
            "set_id": set_id,
            "version": version,
            "pdf_path": self._pdf_path,
            "continuation_pdf_path": self._continuation_pdf_path,
        }
        self.accept()

    def result_data(self) -> dict | None:
        return getattr(self, "_result", None)
