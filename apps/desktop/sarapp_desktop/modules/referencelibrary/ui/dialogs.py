"""Dialogs for the Reference Library."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QPushButton,
    QLabel,
    QFileDialog,
)


class AddEditDialog(QDialog):
    """Add/Edit document dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Document")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.title_edit = QLineEdit()
        self.category_combo = QComboBox()
        self.tags_edit = QLineEdit()
        self.agency_edit = QLineEdit()
        self.jurisdiction_edit = QLineEdit()
        self.desc_edit = QTextEdit()
        self.file_path = QLineEdit()
        browse = QPushButton("Browse")
        browse.clicked.connect(self._choose_file)

        layout.addWidget(QLabel("Title"))
        layout.addWidget(self.title_edit)
        layout.addWidget(QLabel("Category"))
        layout.addWidget(self.category_combo)
        layout.addWidget(QLabel("Tags"))
        layout.addWidget(self.tags_edit)
        layout.addWidget(QLabel("Agency"))
        layout.addWidget(self.agency_edit)
        layout.addWidget(QLabel("Jurisdiction"))
        layout.addWidget(self.jurisdiction_edit)
        layout.addWidget(QLabel("Description"))
        layout.addWidget(self.desc_edit)
        layout.addWidget(QLabel("File"))
        layout.addWidget(self.file_path)
        layout.addWidget(browse)
        buttons = QPushButton("Import")
        buttons.clicked.connect(self.accept)
        layout.addWidget(buttons)

    def _choose_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select file")
        if file_name:
            self.file_path.setText(file_name)
