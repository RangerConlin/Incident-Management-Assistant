from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class QmlPlaceholderDialog(QDialog):
    """Modal dialog indicating a removed QML UI.

    Parameters
    ----------
    component_name: Optional[str]
        Optional title or previous QML component name.
    details: Optional[str]
        Optional extra details to display below the main message.
    parent: Optional[QWidget]
        Parent widget.
    """

    def __init__(
        self,
        component_name: Optional[str] = None,
        details: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(component_name or "QML Placeholder")
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        layout = QVBoxLayout(self)

        title = QLabel("QML used to be here.", self)
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        subtitle = QLabel(
            "You need to replace it with a native PySide6 widget.", self
        )
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        if details:
            details_label = QLabel(details, self)
            details_label.setWordWrap(True)
            details_label.setStyleSheet("color: #666;")
            layout.addWidget(details_label)

        ok_btn = QPushButton("OK", self)
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn, alignment=Qt.AlignmentFlag.AlignCenter)


def show_qml_placeholder(
    title: Optional[str] = None,
    details: Optional[str] = None,
    parent: Optional[QWidget] = None,
) -> int:
    """Show a blocking dialog informing that a QML UI was removed.

    Returns the dialog result (e.g., ``QDialog.Accepted``).
    Creates a local QApplication only if one does not already exist.
    """
    app = QApplication.instance()
    owns_app = False
    if app is None:
        app = QApplication([])
        owns_app = True

    dlg = QmlPlaceholderDialog(component_name=title, details=details, parent=parent)
    result = dlg.exec()

    if owns_app:
        # In library usage, avoid quitting a shared app; only quit if we created it.
        app.quit()

    return result
