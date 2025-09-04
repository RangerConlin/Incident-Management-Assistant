"""Main window for the Reference Library."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QPushButton,
    QLabel,
    QSplitter,
)

from .dialogs import AddEditDialog


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
        filters = QListWidget()
        results = QListWidget()
        preview = QLabel("Select a document to preview")
        splitter.addWidget(filters)
        splitter.addWidget(results)
        splitter.addWidget(preview)

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.addWidget(actions_bar)
        central_layout.addWidget(splitter)
        self.setCentralWidget(central)

    def _open_add_dialog(self) -> None:
        dialog = AddEditDialog(self)
        dialog.exec()
