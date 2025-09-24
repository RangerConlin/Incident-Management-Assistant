"""About page for the settings window."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class AboutPage(QWidget):
    """Static information about the application."""

    def __init__(self, bridge, parent=None):  # noqa: D401 - bridge unused but consistent interface
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Incident Management Assistant\nVersion 3.0")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        title.setWordWrap(True)
        layout.addWidget(title)

        copyright_label = QLabel("© 2024 Incident Management Assistant Team. All rights reserved.")
        copyright_label.setWordWrap(True)
        layout.addWidget(copyright_label)

        license_label = QLabel("License: Proprietary. Contact support for licensing details.")
        license_label.setWordWrap(True)
        layout.addWidget(license_label)

        contact_label = QLabel("Contact: support@incidentassistant.example.com | +1 (555) 010-2048")
        contact_label.setWordWrap(True)
        layout.addWidget(contact_label)

        layout.addStretch(1)
