"""Qt demo showing incident theme switching."""
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel
from styles.adapters.qt_adapter import apply_qt_theme
from styles import styles as core

app = QApplication([])
window = QWidget()
layout = QVBoxLayout(window)

label = QLabel('Incident — Theme Demo')
button = QPushButton('Toggle Theme')

layout.addWidget(label)
layout.addWidget(button)

apply_qt_theme(app, 'light')

modes = ['light', 'dark']

def toggle():
    modes.append(modes.pop(0))
    core.set_theme(modes[0])

button.clicked.connect(toggle)

window.show()
app.exec()
