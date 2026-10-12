"""Public release preview widget."""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QVBoxLayout, QTextBrowser, QWidget

from modules.public_information.services import PublicInformationRepository, build_release_html


class ReleasePreviewWidget(QWidget):
    def __init__(self, repo: PublicInformationRepository | None = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._message: dict[str, Any] | None = None
        self._template: dict[str, Any] | None = None
        layout = QVBoxLayout(self)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        layout.addWidget(self.browser, 1)

    def set_release(self, message: dict[str, Any] | None, template: dict[str, Any] | None = None) -> None:
        self._message = dict(message or {})
        self._template = dict(template or {}) if template else None
        self.browser.setHtml(build_release_html(self._message, self._template))

