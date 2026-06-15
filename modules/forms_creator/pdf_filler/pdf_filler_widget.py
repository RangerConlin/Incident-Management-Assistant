"""Qt widget for configuring and exporting filled PDF forms."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import (
    QFileDialog,
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .mapping_discovery import find_mapping_for_pdf
from .pdf_filler import PDFFiller


class _FillWorker(QThread):
    """Run a PDF fill operation off the UI thread."""

    finished = Signal(list)
    error = Signal(str)

    def __init__(
        self,
        filler: PDFFiller,
        data: dict[str, Any],
        input_pdf: str,
        output_pdf: str,
        strict: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._filler = filler
        self._data = data
        self._input_pdf = input_pdf
        self._output_pdf = output_pdf
        self._strict = strict

    def run(self) -> None:
        try:
            warnings = self._filler.fill(
                self._data,
                self._input_pdf,
                self._output_pdf,
                strict=self._strict,
            )
        except Exception as exc:
            self.error.emit(str(exc))
            return
        self.finished.emit(warnings)


class PDFFillerWidget(QWidget):
    """Widget for selecting templates, previewing mappings, and exporting PDFs."""

    export_complete = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data: dict[str, Any] = {}
        self._filler: PDFFiller | None = None
        self._worker: _FillWorker | None = None
        self._default_output_dir: str | None = None

        self._build_ui()
        self._connect_signals()
        self._update_actions()

    def set_data(self, data: dict[str, Any]) -> None:
        """Replace the incident data used to resolve preview and export values."""
        self._data = data or {}
        self._log("Incident data updated.")
        self._refresh_preview()

    def set_default_output_dir(self, path: str) -> None:
        """Set the default output directory for exported forms."""
        self._default_output_dir = path
        if self.pdf_path_edit.text().strip():
            self._suggest_output_path(self.pdf_path_edit.text().strip())
        elif not self.output_path_edit.text().strip():
            self.output_path_edit.setText(path)
        self._update_actions()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        pdf_row = QHBoxLayout()
        pdf_row.addWidget(QLabel("PDF Template:"))
        self.pdf_path_edit = QLineEdit()
        self.pdf_path_edit.setReadOnly(True)
        self.pdf_path_edit.setPlaceholderText("Select a fillable PDF template…")
        self.pdf_browse_button = QPushButton("Browse…")
        pdf_row.addWidget(self.pdf_path_edit, 1)
        pdf_row.addWidget(self.pdf_browse_button)
        layout.addLayout(pdf_row)

        mapping_row = QHBoxLayout()
        mapping_row.addWidget(QLabel("Mapping Config:"))
        self.mapping_path_edit = QLineEdit()
        self.mapping_path_edit.setReadOnly(True)
        self.mapping_path_edit.setPlaceholderText("Load or auto-discover a JSON mapping…")
        self.mapping_load_button = QPushButton("Load…")
        self.scaffold_button = QPushButton("Generate Scaffold")
        self.scaffold_button.setEnabled(False)
        mapping_row.addWidget(self.mapping_path_edit, 1)
        mapping_row.addWidget(self.mapping_load_button)
        mapping_row.addWidget(self.scaffold_button)
        layout.addLayout(mapping_row)

        self.preview_table = QTableWidget(0, 3)
        self.preview_table.setHorizontalHeaderLabels(["PDF Field", "Source / Path", "Resolved Value"])
        self.preview_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.preview_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.preview_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.preview_table.verticalHeader().setVisible(False)
        header = self.preview_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        self.preview_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.preview_table, 1)

        self.log_panel = QTextEdit()
        self.log_panel.setReadOnly(True)
        self.log_panel.setMaximumHeight(140)
        mono_family = QFontDatabase.systemFont(QFontDatabase.FixedFont).family()
        self.log_panel.setFont(QFont(mono_family, 9))
        layout.addWidget(self.log_panel)

        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("Save to:"))
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("Choose a destination PDF path…")
        self.output_browse_button = QPushButton("Browse…")
        self.export_button = QPushButton("Fill & Export PDF")
        export_font = self.export_button.font()
        export_font.setBold(True)
        self.export_button.setFont(export_font)
        output_row.addWidget(self.output_path_edit, 1)
        output_row.addWidget(self.output_browse_button)
        output_row.addWidget(self.export_button)
        layout.addLayout(output_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

    def _connect_signals(self) -> None:
        self.pdf_browse_button.clicked.connect(self._choose_pdf)
        self.mapping_load_button.clicked.connect(self._choose_mapping)
        self.scaffold_button.clicked.connect(self._generate_scaffold)
        self.output_browse_button.clicked.connect(self._choose_output)
        self.export_button.clicked.connect(self._start_fill)
        self.output_path_edit.textChanged.connect(self._update_actions)

    def _choose_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select PDF Template", "", "PDF Files (*.pdf)")
        if not path:
            return
        self.pdf_path_edit.setText(path)
        self.scaffold_button.setEnabled(True)
        self._log(f"Selected PDF template: {path}")
        self._suggest_output_path(path)

        mapping_path = find_mapping_for_pdf(path)
        if mapping_path:
            self.mapping_path_edit.setText(mapping_path)
            self._log(f"Auto-discovered mapping config: {mapping_path}")
            self._load_mapping(mapping_path)
        else:
            self.mapping_path_edit.clear()
            self._filler = None
            self._log("No mapping config was auto-discovered for the selected PDF.")
            self._refresh_preview()
        self._update_actions()

    def _choose_mapping(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Mapping Config", "", "JSON Files (*.json)")
        if not path:
            return
        self.mapping_path_edit.setText(path)
        self._load_mapping(path)
        self._log(f"Loaded mapping config: {path}")
        self._update_actions()

    def _generate_scaffold(self) -> None:
        pdf_path = self.pdf_path_edit.text().strip()
        if not pdf_path:
            return
        default_name = f"{Path(pdf_path).stem}.mapping.json"
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Mapping Scaffold", default_name, "JSON Files (*.json)")
        if not save_path:
            return
        try:
            PDFFiller.generate_mapping_scaffold(pdf_path, save_path)
        except Exception as exc:
            self._log(f"ERROR generating scaffold: {exc}")
            QMessageBox.critical(self, "Generate Scaffold", str(exc))
            return
        self._log(f"Generated mapping scaffold: {save_path}")

    def _choose_output(self) -> None:
        start_dir = self.output_path_edit.text().strip() or self._default_output_dir or ""
        path, _ = QFileDialog.getSaveFileName(self, "Export Filled PDF", start_dir, "PDF Files (*.pdf)")
        if not path:
            return
        self.output_path_edit.setText(path)
        self._log(f"Output path set: {path}")
        self._update_actions()

    def _load_mapping(self, mapping_path: str) -> None:
        try:
            self._filler = PDFFiller(mapping_path)
        except Exception as exc:
            self._filler = None
            self._log(f"ERROR loading mapping: {exc}")
            QMessageBox.critical(self, "Mapping Load Error", str(exc))
            self._refresh_preview()
            return
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        self.preview_table.setRowCount(0)
        filler = self._filler
        if filler is None:
            return
        rows = filler.preview_rows(self._data)
        unresolved_color = QColor("gray")
        for row_index, row in enumerate(rows):
            self.preview_table.insertRow(row_index)
            for column, key in enumerate(("pdf_field", "source", "resolved")):
                item = QTableWidgetItem(row.get(key, ""))
                if key == "resolved" and not row.get("resolved"):
                    item.setForeground(unresolved_color)
                self.preview_table.setItem(row_index, column, item)
        self.preview_table.resizeColumnsToContents()
        self.preview_table.resizeRowsToContents()
        self._log(f"Preview refreshed with {len(rows)} mapped fields.")
        self._update_actions()

    def _start_fill(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._log("Fill already in progress.")
            return
        input_pdf = self.pdf_path_edit.text().strip()
        output_pdf = self.output_path_edit.text().strip()
        if self._filler is None or not input_pdf or not output_pdf or not self._output_path_ready():
            self._log("Select a valid .pdf output path before exporting.")
            return
        self.progress_bar.show()
        self.export_button.setEnabled(False)
        self._worker = _FillWorker(self._filler, dict(self._data), input_pdf, output_pdf, parent=self)
        self._worker.finished.connect(self._on_fill_finished)
        self._worker.error.connect(self._on_fill_error)
        self._worker.finished.connect(self._cleanup_worker)
        self._worker.error.connect(self._cleanup_worker)
        self._worker.start()
        self._log(f"Started fill/export job for: {output_pdf}")

    def _on_fill_finished(self, warnings: list[str]) -> None:
        output_pdf = self.output_path_edit.text().strip()
        self.progress_bar.hide()
        self._update_actions()
        if warnings:
            for warning in warnings:
                self._log(f"WARNING: {warning}")
        self._log(f"Export completed: {output_pdf}")
        QMessageBox.information(self, "PDF Export Complete", f"Filled PDF exported to:\n{output_pdf}")
        self.export_complete.emit(output_pdf)

    def _on_fill_error(self, message: str) -> None:
        self.progress_bar.hide()
        self._update_actions()
        self._log(f"ERROR during fill/export: {message}")
        QMessageBox.critical(self, "PDF Export Error", message)

    def _cleanup_worker(self, *_args: Any) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()

    def _update_actions(self) -> None:
        has_pdf = bool(self.pdf_path_edit.text().strip())
        has_mapping = self._filler is not None
        has_output = self._output_path_ready()
        is_busy = self._worker is not None and self._worker.isRunning()
        self.scaffold_button.setEnabled(has_pdf and not is_busy)
        self.export_button.setEnabled(has_pdf and has_mapping and has_output and not is_busy)

    def _output_path_ready(self) -> bool:
        output_text = self.output_path_edit.text().strip()
        if not output_text:
            return False
        output_path = Path(output_text)
        if output_path.exists() and output_path.is_dir():
            return False
        return output_path.suffix.lower() == ".pdf"

    def _suggest_output_path(self, pdf_path: str) -> None:
        current_output = self.output_path_edit.text().strip()
        current_path = Path(current_output) if current_output else None
        if current_path and current_path.suffix.lower() == ".pdf":
            return
        target_dir = current_output or self._default_output_dir or str(Path(pdf_path).parent)
        suggested = Path(target_dir) / f"{Path(pdf_path).stem}_filled.pdf"
        self.output_path_edit.setText(str(suggested))

    def _log(self, message: str) -> None:
        self.log_panel.append(message)
        scrollbar = self.log_panel.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
