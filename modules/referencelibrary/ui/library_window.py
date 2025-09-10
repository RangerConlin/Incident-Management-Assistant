"""Main window for the Reference Library."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QSplitter,
    QListWidgetItem,
)

from .dialogs import AddEditDialog
from .widgets import FiltersWidget, ResultsWidget, PreviewWidget


class LibraryWindow(QMainWindow):
    """Reference Library window with filters, results and preview."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Reference Library")
        self._build_ui()

    def _build_ui(self) -> None:
        actions_bar = QWidget()
        actions_layout = QHBoxLayout(actions_bar)
        add_btn = QPushButton("Add")
        actions_layout.addWidget(add_btn)
        actions_layout.addStretch()

        add_btn.clicked.connect(self._open_add_dialog)

        splitter = QSplitter()
        self.filters = FiltersWidget()
        self.results = ResultsWidget()
        self.preview = PreviewWidget()
        splitter.addWidget(self.filters)
        splitter.addWidget(self.results)
        splitter.addWidget(self.preview)

        self.results.currentItemChanged.connect(self._on_result_selected)

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.addWidget(actions_bar)
        central_layout.addWidget(splitter)
        self.setCentralWidget(central)

    def _open_add_dialog(self) -> None:
        dialog = AddEditDialog(self)
        dialog.exec()

    def _on_result_selected(
        self, current: QListWidgetItem | None, previous: QListWidgetItem | None
    ) -> None:
        """Update preview pane when a result is selected."""
        if current is None:
            self.preview.setText("Select a document")
            return
        try:
            # ``ItemCard`` stores extra attributes such as category
            self.preview.setText(current.text())
        except Exception:
            self.preview.setText(str(current))
