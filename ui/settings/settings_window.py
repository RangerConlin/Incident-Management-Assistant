"""Settings window composed of sidebar navigation and stacked pages."""

from __future__ import annotations

from typing import List, Tuple, Type

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .pages import (
    AboutPage,
    AdvancedPage,
    CommunicationsPage,
    DataStoragePage,
    GeneralPage,
    IncidentDefaultsPage,
    MappingPage,
    NotificationsPage,
    PersonnelPage,
    ThemePage,
)

SectionDef = Tuple[str, Type[QWidget]]

SECTIONS: List[SectionDef] = [
    ("General", GeneralPage),
    ("Incident Defaults", IncidentDefaultsPage),
    ("Communications", CommunicationsPage),
    ("Data & Storage", DataStoragePage),
    ("Mapping & GPS", MappingPage),
    ("Personnel & Teams", PersonnelPage),
    ("Theme & Appearance", ThemePage),
    ("Notifications", NotificationsPage),
    ("Advanced", AdvancedPage),
    ("About", AboutPage),
]


class SettingsWindow(QDialog):
    """Modeless settings dialog with live-updating controls."""

    def __init__(self, settings_bridge, parent=None):
        super().__init__(parent)
        self.bridge = settings_bridge
        self.setWindowTitle("Settings")
        self.setModal(False)
        self.resize(980, 620)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        header = self._build_header()
        root.addLayout(header)

        splitter = QSplitter(Qt.Horizontal)
        self.section_list = self._build_section_list()
        splitter.addWidget(self.section_list)

        self.stack = QStackedWidget()
        self._populate_pages()
        splitter.addWidget(self.stack)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        self.section_list.setMinimumWidth(220)

        root.addWidget(splitter)

        self.section_list.setCurrentRow(0)
        self.section_list.setFocus()

    # ------------------------------------------------------------------
    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        title = QLabel("Settings")
        title.setObjectName("settingsWindowTitle")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch(1)

        save_button = QPushButton("Save")
        close_button = QPushButton("Close")
        header.addWidget(save_button)
        header.addWidget(close_button)

        close_button.clicked.connect(self.close)

        if hasattr(self.bridge, "flush") and callable(getattr(self.bridge, "flush")):
            save_button.clicked.connect(self.bridge.flush)
        else:
            save_button.setEnabled(False)

        return header

    def _build_section_list(self) -> QListWidget:
        section_list = QListWidget()
        section_list.setObjectName("settingsSections")
        section_list.setSelectionMode(QListWidget.SingleSelection)
        section_list.setUniformItemSizes(True)

        for name, _widget_cls in SECTIONS:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() & ~Qt.ItemIsDragEnabled)
            section_list.addItem(item)

        section_list.currentRowChanged.connect(self._on_section_changed)
        return section_list

    def _populate_pages(self) -> None:
        for _name, widget_cls in SECTIONS:
            page = widget_cls(self.bridge, self)
            self.stack.addWidget(page)

    # ------------------------------------------------------------------
    def _on_section_changed(self, index: int) -> None:
        if 0 <= index < self.stack.count():
            self.stack.setCurrentIndex(index)

    # ------------------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: D401 - Qt override
        if event.key() == Qt.Key_Escape:
            event.accept()
            self.close()
            return

        if event.key() in (Qt.Key_Up, Qt.Key_Down):
            self.section_list.setFocus()
            QApplication.sendEvent(self.section_list, event)
            return

        super().keyPressEvent(event)
