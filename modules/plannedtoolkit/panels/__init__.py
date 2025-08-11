from __future__ import annotations

import os
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtCore import QUrl


def _load_qml(widget: QWidget, qml_name: str) -> QQuickWidget:
    layout = QVBoxLayout(widget)
    qml_widget = QQuickWidget()
    qml_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "qml", qml_name))
    qml_widget.setSource(QUrl.fromLocalFile(qml_path))
    qml_widget.setResizeMode(QQuickWidget.SizeRootObjectToView)
    layout.addWidget(qml_widget)
    return qml_widget
