"""Item card widget for document display."""

from PySide6.QtWidgets import QListWidgetItem


class ItemCard(QListWidgetItem):
    def __init__(self, title: str, category: str):
        super().__init__(title)
        self.category = category
